import argparse

from kafka import KafkaConsumer

from shared_api.models import Invoice


def run_consume(args):
    for message in KafkaConsumer("invoice.created", bootstrap_servers="kafka:9092"):
        record_entry(Invoice.model_validate_json(message.value))


def run_replay(args):
    ...


def record_entry(invoice: Invoice) -> None:
    ...


def main() -> None:
    parser = argparse.ArgumentParser(prog="ledger-consumer")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run").set_defaults(func=run_consume)
    replay = sub.add_parser("replay")
    replay.add_argument("--from")
    replay.set_defaults(func=run_replay)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
