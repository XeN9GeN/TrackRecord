# Domain model

## Glossary

The Russian column is the wording used in the UI and when talking to customers.

| Term | Russian | Meaning |
|---|---|---|
| **Machine** | Машина | A railway track maintenance (tamping/lining) machine, e.g. "Duomatic 09-32 CSM №67". Identified by *model + factory number*: the number is assigned by the manufacturer and the pair never changes during the machine's life |
| **Machine model** | Модель машины | Series name, e.g. "Duomatic 09-32 CSM". Reference data |
| **Counterparty** | Контрагент | The legal entity that owns the machine (outright, leased, rented, etc.). Our customer: buys equipment from us and orders installation and maintenance |
| **Contact person** | Контактное лицо | An individual representing a counterparty: director, accountant, machine chief, crew chief, etc. A counterparty can have many |
| **Region** | Регион | Approximate location of a counterparty: "Western Kazakhstan", "Far Eastern Railway" |
| **Equipment** | Оборудование | A unit of our equipment installed on a machine. Attributes: type, serial number, production year, software version |
| **Log entry** | Запись лога | Any incoming information about a machine: text, photos, video, audio, documents. Every entry has a common header (who recorded it, when, what kind of event) |
| **Issue** | Замечание | A log entry describing a machine problem or defect. Stays open until another entry (maintenance, repair, consultation) resolves it |
| **Maintenance** | ТО (техническое обслуживание) | Scheduled or on-demand servicing of a machine |

## Entities and relationships

```
Counterparty   1 ── * ContactPerson
Counterparty   1 ── * Machine         (current owner; a machine has exactly one owner at a time)
MachineModel   1 ── * Machine
Machine        1 ── * LogEntry ── * Attachment
Machine        1 ── * Equipment       (currently installed)
EquipmentType  1 ── * Equipment
```

- A machine's owner can change, but at any moment there is only one. Previous owners are visible through "Ownership change" log entries.
- Equipment can be removed and reinstalled many times, by different people and on different machines. All of it is recorded in the log.
- Equipment states: *in stock → installed → removed → … → written off* (no longer on the books).

## Log entry

**Structured header** (database columns, used for rules, filters and search):
machine, author, entry date, event date (may differ from the entry date), kind, title,
source (call, email, messenger, site visit, remote), contact person (who reported it),
machine owner at the time of the entry, issue status.

**Free text:** a description in raw Markdown, written like a messenger message; plain text is
fine. The form suggests a short skeleton per kind (e.g. for an issue: symptoms, when it happens,
what was checked). The author may amend the text later; previous versions are kept (ADR-0008).

**Attachments:** any number of photos, scans, audio, video and documents per entry.
Files are stored outside the database; the entry keeps their metadata (ADR-0007).

**Kinds and their effect on current state:**

| Kind | Russian UI label | Extra fields | Effect |
|---|---|---|---|
| Request / call / info | Обращение / звонок / информация | contact, source | machine's last contact date |
| Issue | Замечание | — | added to the machine's open issues |
| Maintenance / repair / remote consultation | ТО / ремонт / удалённая консультация | issues to resolve | resolves the selected issues |
| Equipment installation | Установка оборудования | equipment, software version | equipment is attached to the machine |
| Equipment removal | Снятие оборудования | equipment | equipment is detached from the machine |
| Equipment write-off | Списание оборудования | equipment | equipment is no longer on the books |
| Software update | Обновление ПО | equipment, software version | equipment's software version |
| Ownership change | Смена владельца | new counterparty | machine's current owner |
| Machine status change | Смена статуса машины | new status | status (in service, under repair, sold, decommissioned) |
| Document | Документ | attachments | — |

**Real-world examples:**
- A depot manager called asking how much maintenance costs (a request: no work was done, but it must be recorded).
- A mechanic sent a video of the machine stalling while moving (issue + video).
- A customer's director reported that the wiring of our system was torn out and asked for connection diagrams (issue).
- The machine was sold and our equipment was removed from it (ownership change + equipment removal).
- An engineer installed new equipment and brought back the signed acceptance certificate (installation + attachment).
- A periodic call to a customer to check the machine's current condition (request).
