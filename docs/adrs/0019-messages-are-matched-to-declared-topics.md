---
status: accepted
date: 2026-11-22
---

# Producers and consumers in code are matched to declared topics and queues

ADR 0004 keeps runtime links in the configuration, and ADR 0018 already matches HTTP calls in code to routes without creating links. Messages follow the same rule. Stage 2f matches a Python producer's send and a consumer's loop or callback to the **declared** `Topic` or `Queue` with the same name, on the broker its connection names. The matches become `Sends` and `Receives` edges from the code to the topic, with `resolved_by: message_match`. It also records the class each side builds or reads as the topic's payload, which feeds the event contract in `impact`.

## Considered options

- **Create topics and queues from the names found in code.** Rejected: a name in code may be a typo, a test topic or another environment's topic, and the graph would grow topics nobody runs. A name with no declared topic raises `MessageWithoutLink` instead.
- **Let reach follow `Sends` and `Receives`.** Rejected: sending a message does not run the handler in this process. `impact` walks across a topic, and says that it does.
- **Keep messages for Later.** Rejected: the main flow of a workspace like Acme runs through a broker, and only a workspace graph can join the function that sends to the function that handles.

## Consequences

- Six libraries are recognised in Release 1: `kafka-python`, `aiokafka`, `confluent-kafka`, `pika`, `aio-pika` and `redis` streams. Names come from stage 2b, so constants, settings defaults and helpers work as they do for HTTP calls.
- A call with more than one candidate, or none, is stored as an unmatched message. Nothing is guessed.
- A sender and a handler that use different classes for the same topic are flagged in the event contract.

Details: [python-parsing.md](../python-parsing.md#messages), [domain-model.md](../domain-model.md#message-payload).
