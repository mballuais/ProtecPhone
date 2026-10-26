"""Real HTTP/Redis checks. Standard library only; no mocked Redis."""
import copy
import json
import os
import socket
import sys
import time
import unittest
import urllib.error
import urllib.request
from decimal import Decimal

PREFIX = os.getenv("REDIS_PREFIX", "protecphone:demo")
URLS = {role: os.getenv(role.upper() + "_URL", "http://localhost:" + port)
        for role, port in [("product", "28081"), ("orders", "28082"), ("sav", "28083")]}


def redis(*args):
    """Small RESP2 client so the demonstration needs no Python packages."""
    with socket.create_connection((os.getenv("REDIS_HOST", "localhost"), int(os.getenv("REDIS_PORT", "6380"))), timeout=5) as connection, connection.makefile("rb") as stream:
        encoded = [str(arg).encode("utf-8") for arg in args]
        connection.sendall(b"*%d\r\n" % len(encoded) + b"".join(
            b"$%d\r\n" % len(arg) + arg + b"\r\n" for arg in encoded))

        def read():
            line = stream.readline()
            if not line:
                raise RuntimeError("Connexion Redis fermee")
            kind, value = line[:1], line[1:-2]
            if kind == b"-":
                raise RuntimeError(value.decode())
            if kind == b"+":
                return value.decode()
            if kind == b":":
                return int(value)
            if kind == b"$":
                size = int(value)
                if size == -1:
                    return None
                data = stream.read(size)
                if stream.read(2) != b"\r\n":
                    raise RuntimeError("Reponse Redis tronquee")
                return data.decode("utf-8")
            if kind == b"*":
                return [read() for _ in range(int(value))]
            raise RuntimeError("Protocole Redis invalide")
        return read()


def key(suffix):
    return PREFIX + ":" + suffix


def api(role, path, data=None, method=None):
    request = urllib.request.Request(URLS[role] + path,
                                    data=None if data is None else json.dumps(data).encode(),
                                    headers={"Content-Type": "application/json"},
                                    method=method or ("GET" if data is None else "POST"))
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        with error:
            detail = error.read().decode()
        raise RuntimeError(f"{role} {path}: HTTP {error.code}: {detail}") from error


def wait(description, predicate, timeout=30):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (RuntimeError, OSError, ValueError) as error:
            last = error
        time.sleep(0.1)
    raise AssertionError(f"Delai depasse ({timeout}s) : {description}. Derniere erreur : {last}")


def idle():
    def complete():
        for role in URLS:
            failures = redis("LRANGE", key("dead:" + role), 0, -1)
            if failures:
                raise AssertionError(f"Messages refuses par {role} : {failures}")
        return all(redis("LLEN", key(kind + ":" + role)) == 0
                   for role in URLS for kind in ["queue", "processing"])
    wait("traitement des files et des messages en cours", complete)


def hashes(suffix):
    values = redis("HGETALL", key(suffix))
    return dict(zip(values[::2], values[1::2]))


def events():
    return [json.loads(raw) for raw in redis("LRANGE", key("events"), 0, -1)]


PRODUCTS = [
    {"produitId": f"coque-{index:03}", "nom": name, "compatibilite": [model],
     "variantes": [{"couleur": color, "prix": price, "stock": stock}]}
    for index, name, model, color, price, stock in [
        (1, "Coque transparente renforcée", "iPhone 15", "noir", 14.99, 80),
        (2, "Coque Samsung Galaxy S24", "Samsung Galaxy S24", "transparent", 19.99, 50),
        (3, "Coque iPhone 16 Pro", "iPhone 16 Pro", "bleu", 24.99, 30),
        (4, "Coque Google Pixel 9", "Google Pixel 9", "rouge", 17.99, 40),
        (5, "Coque Xiaomi 14", "Xiaomi 14", "noir", 12.99, 100),
    ]]
CLIENTS = [{"clientId": client, "nom": name} for client, name in
           [("CLI-7", "Marie Dupont"), ("CLI-8", "Lucas Martin"), ("CLI-9", "Sarah Bernard")]]


def order_data(order_id, product, quantity, client=None):
    variant = product["variantes"][0]
    return {"commandeId": order_id, "dateCommande": "2026-10-07T14:00:00Z",
            "client": client or CLIENTS[0],
            "lignes": [{"produitId": product["produitId"], "nom": product["nom"],
                        "couleur": variant["couleur"], "modele": product["compatibilite"][0],
                        "quantite": quantity, "prixUnitaire": variant["prix"]}],
            "adresseLivraison": "12 rue des Lilas, 75000 Paris, France", "statut": "CONFIRMEE",
            "total": float(Decimal(str(variant["prix"])) * quantity)}


def stock(product_id, replica=False):
    role, path = ("orders", "/replicas/products/") if replica else ("product", "/products/")
    return api(role, path + product_id)["variantes"][0]["stock"]


def demo():
    for role in URLS:
        wait("demarrage " + role, lambda: api(role, "/actuator/health")["status"] == "UP", 90)
    for product in PRODUCTS:
        api("product", "/commands", {"type": "CreateProduct", "payload": product})
    for product in PRODUCTS:
        product_id = product["produitId"]
        assert redis("TYPE", key("product:" + product_id)) == "hash"
        assert redis("HEXISTS", key("product:" + product_id), "variantes") == 1
        assert redis("HGET", key("product:" + product_id), "nom") == product["nom"]
        wait("replique produit " + product_id,
             lambda p=product: api("orders", "/replicas/products/" + p["produitId"]) == p)
    print("OK : cinq Hashes Produit et leurs repliques automatiques", flush=True)
    orders = [order_data(f"CMD-{42 + i}", PRODUCTS[i], quantity, CLIENTS[i])
              for i, quantity in enumerate([2, 1, 3])]
    for order in orders:
        api("orders", "/commands", {"type": "CreateOrder", "payload": order})
    idle()
    for product, expected in zip(PRODUCTS[:3], [78, 49, 27]):
        assert stock(product["produitId"]) == expected
        assert stock(product["produitId"], replica=True) == expected
    for order in orders:
        expected = {k: v for k, v in order.items() if k != "adresseLivraison"}
        assert api("sav", "/replicas/orders/" + order["commandeId"]) == expected
        assert redis("TYPE", key("order:" + order["commandeId"])) == "hash"
    assert len([e for e in events() if e["type"] == "OrderCreated"]) == 3
    print("OK : trois commandes, fan-out Produit/SAV, stocks 78 / 49 / 27", flush=True)
    for ticket_id, order_id, reason in [("SAV-9", "CMD-42", "Coque fissurée à la réception"),
                                         ("SAV-10", "CMD-43", "Mauvaise couleur reçue")]:
        ticket = {"ticketId": ticket_id, "commandeId": order_id,
                  "dateCreation": "2026-10-07T15:30:00Z", "motif": reason, "statut": "EN_COURS",
                  "messages": [{"auteur": "client", "texte": reason, "date": "2026-10-07T15:30:00Z"}]}
        api("sav", "/commands", {"type": "CreateSAVTicket", "payload": ticket})
    api("orders", "/orders/CMD-42/status", {"statut": "EXPEDIEE"}, "PATCH")
    idle()
    assert api("sav", "/replicas/orders/CMD-42")["statut"] == "EXPEDIEE"
    assert hashes("orders:sav-status:SAV-9")["statut"] == "EN_COURS"
    assert redis("TYPE", key("sav:SAV-9")) == "hash"
    print("OK : deux tickets SAV, retour SAV vers Commandes, CMD-42 EXPEDIEE dans SAV", flush=True)
    print(json.dumps({"stocks": {p["produitId"]: stock(p["produitId"]) for p in PRODUCTS},
                      "commande": api("sav", "/replicas/orders/CMD-42"),
                      "evenements": {t: sum(e["type"] == t for e in events()) for t in sorted({e["type"] for e in events()})}},
                     ensure_ascii=False, indent=2), flush=True)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        demo()

    def test_01_hash_creation_and_read(self):
        self.assertEqual(hashes("product:coque-001")["produitId"], "coque-001")
        self.assertEqual(json.loads(redis("HGET", key("product:coque-001"), "variantes"))[0]["stock"], 78)

    def test_02_publication_and_consumption(self):
        idle()
        self.assertTrue(all(e["eventId"] and e["source"] and e["occurredAt"] for e in events()))
        self.assertEqual(len(events()), len({e["eventId"] for e in events()}))
        self.assertGreater(int(redis("HGET", key("metrics:orders"), "processed")), 0)

    def test_03_product_to_orders(self):
        self.assertEqual(api("product", "/products/coque-002"), api("orders", "/replicas/products/coque-002"))

    def test_04_orders_to_product(self):
        self.assertEqual(stock("coque-003"), 27)

    def test_05_orders_to_sav(self):
        self.assertEqual(api("sav", "/replicas/orders/CMD-44")["total"], 74.97)

    def test_06_sav_to_orders(self):
        api("sav", "/tickets/SAV-9/status", {"statut": "RESOLU"}, "PATCH")
        idle()
        self.assertEqual(api("orders", "/orders/CMD-42/sav/SAV-9")["statut"], "RESOLU")

    def test_07_price_and_stock_replication(self):
        api("product", "/products/coque-004/variants", {"couleur": "rouge", "prix": 18.99, "stock": 45}, "PATCH")
        idle()
        variant = api("orders", "/replicas/products/coque-004")["variantes"][0]
        self.assertEqual(variant, {"couleur": "rouge", "prix": 18.99, "stock": 45})
        self.assertIn("PriceChanged", [e["type"] for e in events()])

    def test_08_full_product_update(self):
        product = api("product", "/products/coque-004")
        product["nom"] = "[Edition speciale] Coque Pixel"
        api("product", "/products/coque-004", product, "PUT")
        idle()
        self.assertEqual(api("orders", "/replicas/products/coque-004"), product)
        self.assertIn("ProductUpdated", [e["type"] for e in events()])

    def test_09_duplicate_event_does_not_reduce_stock(self):
        raw = next(raw for raw in redis("LRANGE", key("events"), 0, -1)
                   if json.loads(raw)["type"] == "OrderCreated" and json.loads(raw)["data"]["commandeId"] == "CMD-42")
        before = stock("coque-001")
        redis("RPUSH", key("queue:product"), raw, raw)
        idle()
        self.assertEqual(stock("coque-001"), before)

    def test_10_cancel_once_and_replicate(self):
        api("orders", "/orders/CMD-43/status", {"statut": "ANNULEE"}, "PATCH")
        idle()
        self.assertEqual(stock("coque-002"), 50)
        self.assertEqual(api("sav", "/replicas/orders/CMD-43")["statut"], "ANNULEE")
        raw = next(raw for raw in redis("LRANGE", key("events"), 0, -1) if json.loads(raw)["type"] == "OrderCancelled")
        event = json.loads(raw)
        event["eventId"] = "cancellation-repeated-with-new-id"
        redis("RPUSH", key("queue:product"), raw, json.dumps(event))
        idle()
        self.assertEqual(stock("coque-002"), 50)

    def test_11_return_restock(self):
        for status in ["EXPEDIEE", "LIVREE", "RETOURNEE"]:
            api("orders", "/orders/CMD-44/status", {"statut": status}, "PATCH")
        idle()
        self.assertEqual(stock("coque-003"), 30)
        self.assertEqual(api("sav", "/replicas/orders/CMD-44")["statut"], "RETOURNEE")

    def test_12_invalid_order_does_not_publish(self):
        before = len(events())
        order = order_data("CMD-INVALID", PRODUCTS[0], 900)
        with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
            api("orders", "/orders", order)
        self.assertEqual(len(events()), before)
        self.assertEqual(redis("EXISTS", key("order:CMD-INVALID")), 0)

    def test_13_duplicate_command(self):
        with self.assertRaisesRegex(RuntimeError, "HTTP 409"):
            api("product", "/products", PRODUCTS[0])

    def test_14_multi_line_and_variant_stock(self):
        product = {"produitId": "coque-test", "nom": "Deux variantes", "compatibilite": ["iPhone 15"],
                   "variantes": [{"couleur": "noir", "prix": 10, "stock": 10}, {"couleur": "bleu", "prix": 12, "stock": 20}]}
        api("product", "/products", product)
        idle()
        order = order_data("CMD-TEST", product, 2)
        second = copy.deepcopy(order["lignes"][0])
        second.update(couleur="bleu", prixUnitaire=12, quantite=3)
        order["lignes"].append(second)
        order["total"] = 56
        api("orders", "/orders", order)
        idle()
        self.assertEqual([v["stock"] for v in api("product", "/products/coque-test")["variantes"]], [8, 17])


def reset():
    # The runner stops all three writers before reset; never FLUSHDB/FLUSHALL.
    if PREFIX != "protecphone:demo":
        raise RuntimeError("Reset autorise uniquement pour protecphone:demo")
    cursor = "0"
    keys = []
    while True:
        cursor, batch = redis("SCAN", cursor, "MATCH", PREFIX + ":*", "COUNT", 100)
        keys.extend(batch)
        if cursor == "0":
            break
    for index in range(0, len(keys), 100):
        redis("DEL", *keys[index:index + 100])
    print(f"Reset limite a {PREFIX}:* : {len(keys)} cles", flush=True)


def offline_publish():
    api("product", "/products/coque-005/variants", {"couleur": "noir", "prix": 13.99}, "PATCH")
    assert redis("LLEN", key("queue:orders")) > 0
    assert api("product", "/products/coque-005")["variantes"][0]["prix"] == 13.99
    print("OK : evenement conserve pendant l'arret de Commandes", flush=True)


def offline_verify():
    idle()
    assert api("orders", "/replicas/products/coque-005")["variantes"][0]["prix"] == 13.99
    print("OK : consommateur indisponible puis reprise et synchronisation", flush=True)


def stage_inflight():
    product = api("orders", "/replicas/products/coque-005")
    api("orders", "/orders", order_data("CMD-RECOVERY", product, 2))
    raw = redis("LMOVE", key("queue:product"), key("processing:product"), "LEFT", "RIGHT")
    assert raw and json.loads(raw)["data"]["commandeId"] == "CMD-RECOVERY"
    assert stock_hash("coque-005") == 100
    print("OK : message reclame dans processing, avant son traitement", flush=True)


def stock_hash(product_id):
    return json.loads(redis("HGET", key("product:" + product_id), "variantes"))[0]["stock"]


def recovered():
    idle()
    assert stock("coque-005") == 98
    assert stock("coque-005", True) == 98
    assert api("sav", "/replicas/orders/CMD-RECOVERY")["commandeId"] == "CMD-RECOVERY"
    raw = next(raw for raw in redis("LRANGE", key("events"), 0, -1)
               if json.loads(raw)["type"] == "OrderCreated" and json.loads(raw)["data"]["commandeId"] == "CMD-RECOVERY")
    redis("RPUSH", key("queue:product"), raw)
    idle()
    assert stock("coque-005") == 98
    print("OK : reprise de processing et rejeu idempotent apres redemarrage", flush=True)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if action == "test":
        unittest.main(argv=[sys.argv[0]], verbosity=2)
    else:
        {"demo": demo, "reset": reset, "offline-publish": offline_publish,
         "offline-verify": offline_verify, "stage-inflight": stage_inflight, "recovered": recovered}[action]()
