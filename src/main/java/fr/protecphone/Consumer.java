package fr.protecphone;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;
import java.time.Instant;
import java.util.List;

@Component
public class Consumer {
    private static final Logger LOG = LoggerFactory.getLogger(Consumer.class);
    private final RedisStore store;
    private final Business business;
    private volatile boolean running = true;
    private Thread worker;
    private static final DefaultRedisScript<String> CLAIM = new DefaultRedisScript<>(
            "return redis.call('LMOVE', KEYS[1], KEYS[2], 'LEFT', 'RIGHT')", String.class);
    private static final DefaultRedisScript<Long> REJECT = new DefaultRedisScript<>("""
        redis.call('RPUSH', KEYS[1], ARGV[1])
        return redis.call('LREM', KEYS[2], 1, ARGV[2])
        """, Long.class);

    public Consumer(RedisStore store, Business business) { this.store = store; this.business = business; }
    @PostConstruct
    void start() {
        worker = new Thread(this::run, "consumer-" + store.role);
        worker.start();
    }
    private void run() {
        String pending = store.key("queue:" + store.role);
        String processing = store.key("processing:" + store.role);
        while (running) {
            try {

                String raw = store.redis.opsForList().index(processing, 0);
                if (raw == null) raw = store.redis.execute(CLAIM, List.of(pending, processing));
                if (raw == null) { Thread.sleep(100); continue; }
                try { business.receive(raw); }
                catch (IllegalArgumentException | RedisStore.Missing | RedisStore.Conflict e) {
                    var failed = store.json.createObjectNode().put("raw", raw).put("error", e.getMessage())
                            .put("failedAt", Instant.now().toString());
                    store.redis.execute(REJECT, List.of(store.key("dead:" + store.role), processing), store.encode(failed), raw);
                    LOG.error("Evenement refuse, conserve dans dead:{} : {}", store.role, e.getMessage());
                }
            } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            catch (Exception e) {
                LOG.warn("Redis indisponible ou erreur transitoire, reprise du message : {}", e.getMessage());
                try { Thread.sleep(1000); } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); return; }
            }
        }
    }
    @PreDestroy
    void stop() throws InterruptedException {
        running = false; worker.interrupt(); worker.join(4000);
    }
}
