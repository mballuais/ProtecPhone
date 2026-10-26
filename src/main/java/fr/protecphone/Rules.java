package fr.protecphone;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.HashSet;
import java.util.Set;

final class Rules {
    private Rules() { }
    static void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
    static String text(JsonNode data, String field) {
        require(data.hasNonNull(field) && data.get(field).isTextual() && !data.get(field).asText().isBlank(), "Champ requis : " + field);
        return data.get(field).asText();
    }
    static String id(JsonNode data, String field) {
        String id = text(data, field);
        require(id.matches("[a-zA-Z0-9_-]{1,80}"), "Identifiant invalide : " + field);
        return id;
    }
    static void date(JsonNode data, String field) {
        try { Instant.parse(text(data, field)); }
        catch (Exception e) { throw new IllegalArgumentException("Date ISO-8601 requise : " + field); }
    }
    static void array(JsonNode data, String field) {
        require(data.has(field) && data.get(field).isArray() && !data.get(field).isEmpty(), "Liste non vide requise : " + field);
    }
    static void fields(ObjectNode data, Set<String> names) {
        data.fieldNames().forEachRemaining(field -> require(names.contains(field), "Champ inconnu : " + field));
    }
    static void product(ObjectNode data) {
        fields(data, Set.of("produitId", "nom", "compatibilite", "variantes"));
        id(data, "produitId"); text(data, "nom"); array(data, "compatibilite"); array(data, "variantes");
        data.get("compatibilite").forEach(model -> require(model.isTextual() && !model.asText().isBlank(), "Modele invalide"));
        Set<String> colors = new HashSet<>();
        data.get("variantes").forEach(v -> {
            require(v.isObject(), "Variante invalide");
            require(colors.add(text(v, "couleur")), "Couleur dupliquee");
            require(v.has("prix") && v.get("prix").isNumber() && v.get("prix").decimalValue().signum() >= 0, "Prix invalide");
            require(v.has("stock") && v.get("stock").isIntegralNumber() && v.get("stock").canConvertToInt() && v.get("stock").asInt() >= 0, "Stock invalide");
        });
    }
    static ObjectNode variant(ObjectNode product, String color) {
        for (JsonNode variant : product.withArray("variantes")) if (variant.path("couleur").asText().equals(color)) return (ObjectNode) variant;
        throw new IllegalArgumentException("Couleur absente du produit : " + color);
    }
    static BigDecimal money(JsonNode value) {
        require(value != null && value.isNumber() && value.decimalValue().signum() >= 0, "Montant invalide");
        return value.decimalValue();
    }
}
