package fr.protecphone;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.*;

@Component
public class RedisStore {
    public final StringRedisTemplate redis;
    public final ObjectMapper json;
    public final String prefix;
    public final String role;

    // State changes, fan-out, deduplication and acknowledgement share one Redis transaction.
    // No process can crash between modifying stock and recording a processed event.
    private static final DefaultRedisScript<Long> COMMIT = new DefaultRedisScript<>("""
        local p = cjson.decode(ARGV[1])
        if p.eventId ~= '' and redis.call('HEXISTS', KEYS[1], p.eventId) == 1 then
            redis.call('LREM', KEYS[2], 1, p.raw)
            return 0
        end
        for _, g in ipairs(p.guards) do
            local value = redis.call('HGET', g.key, g.field)
            if (g.absent and value) or (not g.absent and value ~= g.value) then return -1 end
        end
        for _, w in ipairs(p.writes) do
            for field, value in pairs(w.fields) do redis.call('HSET', w.key, field, value) end
        end
        for _, e in ipairs(p.events) do
            for _, destination in ipairs(e.destinations) do
                redis.call('RPUSH', destination, e.raw)
            end
            redis.call('RPUSH', KEYS[3], e.raw)
        end
        if p.eventId ~= '' then
            redis.call('HSET', KEYS[1], p.eventId, p.time)
            redis.call('HINCRBY', KEYS[4], 'processed', 1)
            redis.call('LREM', KEYS[2], 1, p.raw)
        end
        return 1
        """, Long.class);

    public RedisStore(StringRedisTemplate redis, ObjectMapper json,
                      @Value("${protecphone.prefix}") String prefix,
                      @Value("${protecphone.role}") String role) {
        if (!Set.of("product", "orders", "sav").contains(role)) throw new IllegalArgumentException("SERVICE_ROLE invalide");
        if (!prefix.matches("[a-zA-Z0-9:_-]+")) throw new IllegalArgumentException("REDIS_PREFIX invalide");
        this.redis = redis; this.json = json; this.prefix = prefix; this.role = role;
    }

    public String key(String suffix) { return prefix + ":" + suffix; }
    public String encode(Object value) {
        try { return json.writeValueAsString(value); }
        catch (Exception e) { throw new IllegalArgumentException("JSON invalide", e); }
    }
    public ObjectNode parse(String raw) {
        try {
            JsonNode node = json.readTree(raw);
            if (!(node instanceof ObjectNode object)) throw new IllegalArgumentException("Objet JSON requis");
            return object;
        } catch (Exception e) { throw new IllegalArgumentException("Objet JSON invalide", e); }
    }

    public ObjectNode read(String suffix) {
        Map<Object, Object> fields = redis.opsForHash().entries(key(suffix)); // HGETALL
        if (fields.isEmpty()) throw new Missing("Introuvable : " + suffix);
        ObjectNode result = json.createObjectNode();
        fields.forEach((field, value) -> {
            String text = value.toString();
            String name = field.toString();
            if (Set.of("compatibilite", "variantes", "client", "lignes", "messages", "total", "stock", "prix").contains(name)) {
                try { result.set(name, json.readTree(text)); }
                catch (Exception e) { throw new IllegalStateException("Champ Redis invalide : " + name, e); }
            } else result.put(name, text);
        });
        return result;
    }
    public boolean exists(String suffix, String field) { return redis.opsForHash().hasKey(key(suffix), field); }

    public Plan plan() { return new Plan(); }
    public class Plan {
        public final List<Map<String, Object>> writes = new ArrayList<>();
        public final List<Map<String, Object>> guards = new ArrayList<>();
        public final List<Map<String, Object>> events = new ArrayList<>();
        public void absent(String suffix, String field) {
            guards.add(Map.of("key", key(suffix), "field", field, "absent", true));
        }
        public void write(String suffix, ObjectNode data) {
            Map<String, String> fields = new LinkedHashMap<>();
            data.fields().forEachRemaining(entry -> fields.put(entry.getKey(), entry.getValue().isTextual()
                    ? entry.getValue().asText() : encode(entry.getValue())));
            writes.add(Map.of("key", key(suffix), "fields", fields));
        }
        public void event(String type, ObjectNode data) {
            List<String> recipients = recipients(type);
            ObjectNode event = json.createObjectNode();
            event.put("eventId", UUID.randomUUID().toString());
            event.put("type", type); event.put("source", role);
            event.put("occurredAt", Instant.now().toString()); event.set("data", data.deepCopy());
            events.add(Map.of("raw", encode(event), "destinations", recipients.stream().map(r -> key("queue:" + r)).toList()));
        }
        public void commit() { commit("", ""); }
        public void commit(String eventId, String raw) {
            Map<String, Object> p = Map.of("writes", writes, "guards", guards, "events", events,
                    "eventId", eventId, "raw", raw, "time", Instant.now().toString());
            Long result = redis.execute(COMMIT, List.of(key("processed:" + role), key("processing:" + role),
                    key("events"), key("metrics:" + role)), encode(p));
            if (result == null || result < 0) throw new Conflict("Identifiant deja utilise");
        }
    }

    public static List<String> recipients(String type) {
        return switch (type) {
            case "ProductCreated", "ProductUpdated", "PriceChanged", "StockChanged", "AfterSalesStatusChanged" -> List.of("orders");
            case "OrderCreated", "OrderCancelled" -> List.of("product", "sav");
            case "OrderStatusChanged" -> List.of("sav");
            case "ProductReturned" -> List.of("product");
            default -> throw new IllegalArgumentException("Evenement inconnu : " + type);
        };
    }
    public static String emitter(String type) {
        return switch (type) {
            case "ProductCreated", "ProductUpdated", "PriceChanged", "StockChanged" -> "product";
            case "AfterSalesStatusChanged" -> "sav";
            case "OrderCreated", "OrderCancelled", "OrderStatusChanged", "ProductReturned" -> "orders";
            default -> throw new IllegalArgumentException("Evenement inconnu : " + type);
        };
    }
    public static class Missing extends RuntimeException { public Missing(String message) { super(message); } }
    public static class Conflict extends RuntimeException { public Conflict(String message) { super(message); } }
}
