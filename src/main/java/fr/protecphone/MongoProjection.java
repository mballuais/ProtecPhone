package fr.protecphone;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.mongodb.client.model.ReplaceOptions;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;
import java.util.List;
import java.util.Set;

/** Durable FIFO outbox: acknowledge only after all Mongo replacements succeed. */
@Component
public class MongoProjection {
    private static final Logger LOG = LoggerFactory.getLogger(MongoProjection.class);
    private static final DefaultRedisScript<String> CLAIM = new DefaultRedisScript<>(
            "return redis.call('LMOVE', KEYS[1], KEYS[2], 'LEFT', 'RIGHT')", String.class);
    private final RedisStore store;
    private final MongoTemplate mongo;
    private volatile boolean running = true;
    private Thread worker;

    public MongoProjection(RedisStore store, MongoTemplate mongo) { this.store = store; this.mongo = mongo; }

    static String collection(String suffix) {
        if (suffix.startsWith("replica:product:")) return "product_replicas";
        if (suffix.startsWith("replica:order:")) return "order_replicas";
        if (suffix.startsWith("product:allocation:")) return "stock_allocations";
        if (suffix.startsWith("orders:sav-status:")) return "sav_status_replicas";
        if (suffix.startsWith("product:")) return "products";
        if (suffix.startsWith("order:")) return "orders";
        if (suffix.startsWith("sav:")) return "sav_tickets";
        throw new IllegalArgumentException("Projection inconnue : " + suffix);
    }

    public ObjectNode read(String collection, String id) {
        String suffix = switch (collection) {
            case "products" -> "product:";
            case "orders" -> "order:";
            case "sav_tickets" -> "sav:";
            case "product_replicas" -> "replica:product:";
            case "order_replicas" -> "replica:order:";
            default -> throw new RedisStore.Missing("Collection absente");
        };
        boolean allowed = switch (store.role) {
            case "product" -> collection.equals("products");
            case "orders" -> Set.of("orders", "product_replicas").contains(collection);
            case "sav" -> Set.of("sav_tickets", "order_replicas").contains(collection);
            default -> false;
        };
        if (!allowed) throw new RedisStore.Missing("Collection absente de ce service");
        Document result = mongo.getCollection(collection).find(new Document("_id", store.key(suffix + id))).first();
        if (result == null) throw new RedisStore.Missing("Projection pas encore disponible : " + id);
        result.remove("_id"); result.remove("_namespace");
        return store.parse(result.toJson());
    }

    @PostConstruct
    void start() { worker = new Thread(this::run, "mongo-projection-" + store.role); worker.start(); }

    private void run() {
        String pending = store.key("mongo:queue:" + store.role);
        String processing = store.key("mongo:processing:" + store.role);
        while (running) {
            try {
                String raw = store.redis.opsForList().index(processing, 0);
                if (raw == null) raw = store.redis.execute(CLAIM, List.of(pending, processing));
                if (raw == null) { Thread.sleep(100); continue; }
                JsonNode batch = store.json.readTree(raw);
                for (JsonNode write : batch) {
                    String suffix = write.path("suffix").asText();
                    Document document = Document.parse(store.encode(write.get("document")));
                    document.put("_id", store.key(suffix));
                    document.put("_namespace", store.prefix);
                    mongo.getCollection(collection(suffix)).replaceOne(new Document("_id", store.key(suffix)),
                            document, new ReplaceOptions().upsert(true));
                }
                store.redis.opsForList().remove(processing, 1, raw);
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            catch (Exception e) {
                LOG.warn("Projection MongoDB en attente, reprise sans acquittement : {}", e.getMessage());
                try { Thread.sleep(1000); }
                catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); return; }
            }
        }
    }

    @PreDestroy
    void stop() throws InterruptedException { running = false; worker.interrupt(); worker.join(5000); }
}
