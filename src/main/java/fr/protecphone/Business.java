package fr.protecphone;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;
import java.util.*;
import static fr.protecphone.Rules.*;

@Service
public class Business {
    private final RedisStore store;
    public Business(RedisStore store) { this.store = store; }

    void role(String expected) {
        if (!store.role.equals(expected)) throw new RedisStore.Missing("Route absente de ce service");
    }
    public synchronized ObjectNode product(ObjectNode data, boolean create) {
        role("product"); Rules.product(data);
        String key = "product:" + id(data, "produitId");
        var plan = store.plan();
        if (create) plan.absent(key, "produitId"); else store.read(key);
        plan.write(key, data); plan.event(create ? "ProductCreated" : "ProductUpdated", data); plan.commit();
        return data;
    }
    public synchronized ObjectNode variant(String productId, ObjectNode patch) {
        role("product"); fields(patch, Set.of("couleur", "prix", "stock"));
        ObjectNode data = store.read("product:" + productId);
        ObjectNode variant = Rules.variant(data, text(patch, "couleur"));
        require(patch.has("prix") || patch.has("stock"), "Prix ou stock requis");
        if (patch.has("prix")) variant.set("prix", patch.get("prix"));
        if (patch.has("stock")) variant.set("stock", patch.get("stock"));
        Rules.product(data);
        var plan = store.plan(); plan.write("product:" + productId, data);
        if (patch.has("prix")) plan.event("PriceChanged", data);
        if (patch.has("stock")) plan.event("StockChanged", data);
        plan.commit(); return data;
    }
    public synchronized ObjectNode order(ObjectNode data) {
        role("orders");
        fields(data, Set.of("commandeId", "dateCommande", "client", "lignes", "adresseLivraison", "statut", "total"));
        String orderId = id(data, "commandeId"); date(data, "dateCommande");
        require(data.path("client").isObject(), "Client requis"); id(data.get("client"), "clientId"); text(data.get("client"), "nom");
        text(data, "adresseLivraison"); array(data, "lignes");
        if (!data.has("statut")) data.put("statut", "CONFIRMEE");
        require(text(data, "statut").equals("CONFIRMEE"), "Statut initial attendu : CONFIRMEE");
        BigDecimal total = BigDecimal.ZERO;
        Map<String, Integer> quantities = new HashMap<>();
        for (JsonNode line : data.get("lignes")) {
            require(line.isObject(), "Ligne invalide");
            String productId = id(line, "produitId"); String color = text(line, "couleur");
            require(line.path("quantite").isIntegralNumber() && line.path("quantite").canConvertToInt() && line.get("quantite").asInt() > 0, "Quantite invalide");
            ObjectNode product = store.read("replica:product:" + productId);
            require(product.path("nom").asText().equals(text(line, "nom")), "Nom produit incorrect");
            String model = text(line, "modele");
            boolean compatible = false;
            for (JsonNode candidate : product.withArray("compatibilite")) if (candidate.asText().equals(model)) compatible = true;
            require(compatible, "Modele incompatible");
            ObjectNode variant = Rules.variant(product, color);
            BigDecimal price = money(line.get("prixUnitaire"));
            require(price.compareTo(money(variant.get("prix"))) == 0, "Prix different de la replique");
            int quantity = quantities.merge(productId + ":" + color, line.get("quantite").asInt(), Math::addExact);
            require(quantity <= variant.path("stock").asInt(), "Stock insuffisant dans la replique");
            total = total.add(price.multiply(BigDecimal.valueOf(line.get("quantite").asInt())));
        }
        if (data.has("total")) require(money(data.get("total")).compareTo(total) == 0, "Total incorrect");
        data.put("total", total);
        var plan = store.plan(); plan.absent("order:" + orderId, "commandeId");
        plan.write("order:" + orderId, data); plan.event("OrderCreated", data); plan.commit(); return data;
    }
    public synchronized ObjectNode orderStatus(String orderId, ObjectNode patch) {
        role("orders"); fields(patch, Set.of("statut")); String status = text(patch, "statut");
        require(Set.of("EXPEDIEE", "LIVREE", "RETOURNEE", "ANNULEE").contains(status), "Statut commande invalide");
        ObjectNode data = store.read("order:" + orderId);
        String previous = data.path("statut").asText();
        if (previous.equals(status)) return data;
        require(switch (previous) {
            case "CONFIRMEE" -> Set.of("EXPEDIEE", "ANNULEE").contains(status);
            case "EXPEDIEE" -> status.equals("LIVREE");
            case "LIVREE" -> status.equals("RETOURNEE");
            default -> false;
        }, "Transition de statut impossible");
        data.put("statut", status);
        var plan = store.plan(); plan.write("order:" + orderId, data);
        if (status.equals("ANNULEE")) plan.event("OrderCancelled", data);
        else {
            plan.event("OrderStatusChanged", store.json.createObjectNode().put("commandeId", orderId).put("statut", status));
            if (status.equals("RETOURNEE")) plan.event("ProductReturned", data);
        }
        plan.commit(); return data;
    }
    public synchronized ObjectNode ticket(ObjectNode data) {
        role("sav"); fields(data, Set.of("ticketId", "commandeId", "dateCreation", "motif", "statut", "messages"));
        String ticketId = id(data, "ticketId"); String orderId = id(data, "commandeId");
        store.read("replica:order:" + orderId); date(data, "dateCreation"); text(data, "motif");
        require(Set.of("OUVERT", "EN_COURS").contains(text(data, "statut")), "Statut SAV initial invalide");
        array(data, "messages");
        for (JsonNode message : data.get("messages")) {
            require(message.isObject(), "Message invalide"); text(message, "auteur"); text(message, "texte"); date(message, "date");
        }
        var plan = store.plan(); plan.absent("sav:" + ticketId, "ticketId"); plan.write("sav:" + ticketId, data);
        plan.event("AfterSalesStatusChanged", ticketEvent(data)); plan.commit(); return data;
    }
    public synchronized ObjectNode ticketStatus(String ticketId, ObjectNode patch) {
        role("sav"); fields(patch, Set.of("statut")); String status = text(patch, "statut");
        require(Set.of("OUVERT", "EN_COURS", "RESOLU").contains(status), "Statut SAV invalide");
        ObjectNode data = store.read("sav:" + ticketId); data.put("statut", status);
        var plan = store.plan(); plan.write("sav:" + ticketId, data); plan.event("AfterSalesStatusChanged", ticketEvent(data)); plan.commit(); return data;
    }
    private ObjectNode ticketEvent(ObjectNode data) {
        return store.json.createObjectNode().put("ticketId", data.path("ticketId").asText())
                .put("commandeId", data.path("commandeId").asText()).put("statut", data.path("statut").asText());
    }

    public synchronized void receive(String raw) {
        ObjectNode event = store.parse(raw); String eventId = id(event, "eventId");
        String type = text(event, "type");
        require(RedisStore.recipients(type).contains(store.role), "Mauvais destinataire");
        require(RedisStore.emitter(type).equals(text(event, "source")), "Emetteur incorrect");
        require(event.path("data").isObject(), "Donnees evenement absentes");
        var plan = store.plan();
        if (store.exists("processed:" + store.role, eventId)) { plan.commit(eventId, raw); return; }
        ObjectNode data = (ObjectNode) event.get("data");
        if (store.role.equals("orders")) {
            if (type.equals("AfterSalesStatusChanged")) {
                store.read("order:" + id(data, "commandeId"));
                plan.write("orders:sav-status:" + id(data, "ticketId"), data);
            } else {
                Rules.product(data); // Full variant snapshots preserve prices/stocks per colour.
                plan.write("replica:product:" + id(data, "produitId"), data);
            }
        } else if (store.role.equals("sav")) {
            String orderId = id(data, "commandeId");
            ObjectNode replica;
            if (type.equals("OrderCreated")) {
                replica = data.deepCopy(); replica.remove("adresseLivraison");
            } else {
                replica = store.read("replica:order:" + orderId);
                replica.put("statut", text(data, "statut"));
            }
            plan.write("replica:order:" + orderId, replica);
        } else stock(type, data, plan);
        plan.commit(eventId, raw);
    }

    private void stock(String type, ObjectNode order, RedisStore.Plan plan) {
        String orderId = id(order, "commandeId");
        String allocation = "product:allocation:" + orderId;
        String state = store.exists(allocation, "state") ? store.read(allocation).path("state").asText() : "NONE";
        // Business-level protection also covers repeated cancellation/return commands with a new event ID.
        if (type.equals("OrderCreated") && !state.equals("NONE")) return;
        if (!type.equals("OrderCreated") && !state.equals("ALLOCATED")) return;
        array(order, "lignes");
        if (!type.equals("OrderCreated")) {
            JsonNode allocatedLines = store.read(allocation).get("lignes");
            require(allocatedLines.equals(order.get("lignes")), "Lignes differentes de la reservation");
        }
        Map<String, ObjectNode> products = new LinkedHashMap<>();
        for (JsonNode line : order.get("lignes")) {
            String productId = id(line, "produitId");
            ObjectNode product = products.computeIfAbsent(productId, id -> store.read("product:" + id));
            ObjectNode variant = Rules.variant(product, text(line, "couleur"));
            require(line.path("quantite").isIntegralNumber() && line.path("quantite").asInt() > 0, "Quantite invalide");
            int delta = line.get("quantite").asInt() * (type.equals("OrderCreated") ? -1 : 1);
            int stock = Math.addExact(variant.path("stock").asInt(), delta);
            require(stock >= 0, "Stock reel insuffisant : " + productId);
            variant.put("stock", stock);
        }
        products.forEach((productId, data) -> { plan.write("product:" + productId, data); plan.event("StockChanged", data); });
        ObjectNode ledger = store.json.createObjectNode().put("commandeId", orderId)
                .put("state", type.equals("OrderCreated") ? "ALLOCATED" : type.equals("OrderCancelled") ? "CANCELLED" : "RETURNED");
        ledger.set("lignes", order.get("lignes")); plan.write(allocation, ledger);
    }
}
