"""Start Docker, seed via business APIs, verify flows and exercise real restarts."""
import argparse
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True)


def check(action):
    compose("run", "--rm", "--no-deps", "checks", action)


def mongo_query(expression):
    compose("exec", "-T", "mongodb", "mongosh", "protecphone", "--quiet", "--eval", expression)


def mongo_reset():
    # Never drop a database: only documents in the reserved demo namespace.
    marker = "protecphone:validation:" + str(uuid.uuid4())
    mongo_query("const marker='" + marker + "'; "
                "db.products.insertOne({_id:marker,_namespace:marker,preuve:'a conserver'}); try { "
                "for (const c of ['products','orders','sav_tickets','product_replicas',"
                "'order_replicas','stock_allocations','sav_status_replicas']) "
                "print(c, db.getCollection(c).deleteMany({_namespace:'protecphone:demo'}).deletedCount); "
                "if(!db.products.findOne({_id:marker})) throw Error('Donnee hors namespace supprimee'); "
                "print('OK : reset MongoDB preserve les donnees hors namespace'); "
                "} finally {db.products.deleteOne({_id:marker});}")


def mongo_reads():
    mongo_query("const q={_namespace:'protecphone:demo'}; "
                "for(const [c,n] of Object.entries({products:5,orders:3,sav_tickets:2,product_replicas:5,order_replicas:3})) "
                "{const count=db.getCollection(c).countDocuments(q); if(count!==n) throw Error(c+': '+count); print(c+': '+count+' OK');} "
                "printjson(db.products.findOne({...q,produitId:'coque-001'})); "
                "printjson(db.orders.find({...q,'client.clientId':'CLI-7'}).toArray()); "
                "const r=db.order_replicas.findOne({...q,commandeId:'CMD-42'}); "
                "if(r.statut!=='EXPEDIEE') throw Error('statut replique'); printjson(r)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["demo", "test"], nargs="?", default="demo")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    # Stop writers before deleting the isolated demonstration namespace.
    compose("up", "-d", "--wait", "redis", "mongodb")
    compose("stop", "product", "orders", "sav")
    check("reset")
    mongo_reset()
    build = [] if args.no_build else ["--build"]
    compose("up", *build, "-d", "--wait", "product", "orders", "sav")
    check("demo")
    mongo_reads()
    if args.action == "test":
        check("test")
    if args.action == "test":
        try:
            compose("stop", "orders")
            check("offline-publish")
            compose("up", "-d", "--wait", "orders")
            check("offline-verify")
            compose("stop", "product")
            check("stage-inflight")
            # Redis persistence is tested with an actual restart while the event is in flight.
            compose("restart", "redis")
            compose("up", "-d", "--wait", "redis", "product", "orders", "sav")
            check("recovered")
            compose("restart", "mongodb")
            compose("up", "-d", "--wait", "mongodb")
            check("mongo-verify")
            compose("stop", "mongodb")
            check("mongo-offline")
            # Restart the owner while Mongo is down: its persistent outbox must survive.
            compose("restart", "product")
            compose("up", "-d", "--wait", "mongodb")
            check("mongo-recovered")
            compose("kill", "-s", "SIGKILL", "product")
            compose("up", "-d", "--wait", "product")
            check("recovered")
            mongo_query("const q={_namespace:'protecphone:demo'}; "
                        "for(const [c,n] of Object.entries({products:6,orders:5,sav_tickets:2,product_replicas:6,order_replicas:5})) "
                        "{const count=db.getCollection(c).countDocuments(q); if(count!==n) throw Error(c+': '+count); "
                        "print('OK : apres rejeux et reprises '+c+' = '+count);}")
            print("OK : suite Redis/MongoDB + reprise des services, persistance des deux bases, panne MongoDB et arret brutal", flush=True)
        finally:
            compose("up", "-d", "--wait", "product", "orders", "sav")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"ECHEC : commande Docker terminee avec le code {error.returncode}", file=sys.stderr)
        compose("logs", "--tail", "40", "product", "orders", "sav")
        sys.exit(error.returncode)
