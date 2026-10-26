package fr.protecphone;

import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import java.time.Instant;
import java.util.Map;

@RestController
public class Api {
    private final Business business;
    private final RedisStore store;
    public Api(Business business, RedisStore store) { this.business = business; this.store = store; }

    @PostMapping("/products") @ResponseStatus(HttpStatus.CREATED)
    ObjectNode product(@RequestBody ObjectNode data) { return business.product(data, true); }
    @PutMapping("/products/{id}")
    ObjectNode updateProduct(@PathVariable String id, @RequestBody ObjectNode data) {
        Rules.require(id.equals(Rules.id(data, "produitId")), "Identifiants differents");
        return business.product(data, false);
    }
    @PatchMapping("/products/{id}/variants")
    ObjectNode variant(@PathVariable String id, @RequestBody ObjectNode patch) { return business.variant(id, patch); }
    @GetMapping("/products/{id}")
    ObjectNode getProduct(@PathVariable String id) { business.role("product"); return store.read("product:" + id); }
    @GetMapping("/replicas/products/{id}")
    ObjectNode productReplica(@PathVariable String id) { business.role("orders"); return store.read("replica:product:" + id); }
    @PostMapping("/orders") @ResponseStatus(HttpStatus.CREATED)
    ObjectNode order(@RequestBody ObjectNode data) { return business.order(data); }
    @GetMapping("/orders/{id}")
    ObjectNode getOrder(@PathVariable String id) { business.role("orders"); return store.read("order:" + id); }
    @PatchMapping("/orders/{id}/status")
    ObjectNode orderStatus(@PathVariable String id, @RequestBody ObjectNode patch) { return business.orderStatus(id, patch); }
    @GetMapping("/replicas/orders/{id}")
    ObjectNode orderReplica(@PathVariable String id) { business.role("sav"); return store.read("replica:order:" + id); }
    @PostMapping("/tickets") @ResponseStatus(HttpStatus.CREATED)
    ObjectNode ticket(@RequestBody ObjectNode data) { return business.ticket(data); }
    @GetMapping("/tickets/{id}")
    ObjectNode getTicket(@PathVariable String id) { business.role("sav"); return store.read("sav:" + id); }
    @PatchMapping("/tickets/{id}/status")
    ObjectNode ticketStatus(@PathVariable String id, @RequestBody ObjectNode data) { return business.ticketStatus(id, data); }
    @GetMapping("/orders/{id}/sav/{ticketId}")
    ObjectNode savStatus(@PathVariable String id, @PathVariable String ticketId) {
        business.role("orders"); var status = store.read("orders:sav-status:" + ticketId);
        Rules.require(id.equals(status.path("commandeId").asText()), "Ticket d'une autre commande"); return status;
    }
    // Executes the three JSON command envelopes already present in the repository.
    @PostMapping("/commands") @ResponseStatus(HttpStatus.CREATED)
    ObjectNode command(@RequestBody ObjectNode command) {
        Rules.require(command.path("payload").isObject(), "payload requis");
        ObjectNode data = (ObjectNode) command.get("payload");
        return switch (Rules.text(command, "type")) {
            case "CreateProduct" -> business.product(data, true);
            case "CreateOrder" -> business.order(data);
            case "CreateSAVTicket" -> business.ticket(data);
            default -> throw new IllegalArgumentException("Commande inconnue");
        };
    }
    @ExceptionHandler(IllegalArgumentException.class) @ResponseStatus(HttpStatus.BAD_REQUEST)
    Map<String, String> invalid(IllegalArgumentException e) { return error(e); }
    @ExceptionHandler(RedisStore.Missing.class) @ResponseStatus(HttpStatus.NOT_FOUND)
    Map<String, String> missing(RedisStore.Missing e) { return error(e); }
    @ExceptionHandler(RedisStore.Conflict.class) @ResponseStatus(HttpStatus.CONFLICT)
    Map<String, String> conflict(RedisStore.Conflict e) { return error(e); }
    private Map<String, String> error(Exception e) { return Map.of("error", e.getMessage(), "time", Instant.now().toString()); }
}
