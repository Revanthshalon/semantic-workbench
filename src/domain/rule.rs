//! The rule ids of the domain model, so that an error or a test can name the rule it is about.
//!
//! Every rule table of `docs/domain-model.md` is copied below, one section per group. The last
//! column says where a rule is enforced:
//!
//! - **Type**: the Rust types cannot hold a broken value, so there is nothing to check.
//! - **Build**: building the value is refused. A broken value can never exist.
//! - **Graph**: the rule needs the whole graph, so it is checked by one `validate` pass over a
//!   finished graph.
//! - **Indexer**: the indexer keeps the rule by how it runs, such as what it reads again or
//!   replaces on each index. No value is checked against it.
//!
//! ## Node
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | N1 | `name` and `qualified_name` are not empty | Type |
//! | N2 | The id equals the hash of the five inputs. A node cannot be built with any other id | Build |
//! | N3 | The scope suits the kind, as in the Scope table | Build |
//! | N4 | A code node is always `Parsed`. `Workspace`, `Project`, `Binary`, `Topic` and `Queue` are always `Declared`. The other workspace kinds may be either | Build |
//! | N5 | Building the same node twice from the same inputs gives the same id | Build |
//! | N6 | No two nodes in a graph share an id | Graph |
//! | N7 | There is exactly one `Workspace` node | Graph |
//! | N8 | The data suits the kind, as in the node data table | Type |
//! | N9 | A code node's data suits the language of the file it is parsed from, and a binary's framework suits its project's language, as in the language table. The language is given when the node is built and is not stored on it | Build |
//! | N10 | A role suits the kind, as in the role table. `app` is given only when `framework` is `Fastapi` | Build for the role, Type for `app` |
//!
//! ## Edge
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | E1 | A workspace edge connects only the node kinds its row allows in the workspace edge table. `Edge::new` takes the two end nodes, not their ids, so that it can check this | Build |
//! | E2 | A workspace edge never starts and ends at the same node | Build |
//! | E3 | The provenance suits the kind, as in the table above | Build |
//! | E4 | `note` appears only on a `Declared` edge | Type |
//! | E5 | Both ends of every edge are nodes in the graph | Graph |
//! | E6 | No two edges share source, target, kind and site. Two calls from one function to another on different lines are two edges | Graph |
//! | E7 | There is at most one `DependsOn` edge from one project to another. When the manifest and the configuration both name the pair, the declared one is kept | Graph |
//! | E8 | A `Service` has exactly one of `Runs` or `BuiltFrom`. An `ExternalService` has neither | Graph |
//! | E9 | A `Binary` has exactly one `EntryPoint`, and it leads to a `File` of the same project | Graph |
//! | E10 | A `Runs` edge leads to a binary of the project whose folder the service is built from | Graph |
//! | E11 | A framework edge joins only these: `Mounts` from a `Variable` with role `App` or `Router` to such a `Variable` or to a `Route`. `Handles` from a `Route` to a `Function` or `Method`. `Injects` from a `Function`, `Method`, `Route` or `Variable` with role `Router` to a `Function`, `Method` or `Class`. `Requests` from a `Function`, `Method` or `File` to a `Route`. `Handles` may also start at a `Command`. `Sends` from a `Function`, `Method` or `File`, and `Receives` from a `Function` or `Method`, to a `Topic` or `Queue` | Graph |
//! | E12 | An edge with `resolved_by: Flow` rests on at least one inferred type: of a parameter of its callable, of the return of a function its receiver came from, of a field, or of a name bound more than once | Graph |
//! | E13 | `resolved_by` is given only on a code edge with provenance `TreeSitter` or `Scip`, and on `Invokes` (provenance `Compose` or `Dockerfile`). `Flow` is given only on `Calls` and `Instantiates`. `Framework` is given only on `Mounts`, `Handles` and `Injects`, and those three always have it. `RouteMatch` is given only on `Requests`, `MessageMatch` only on `Sends` and `Receives`, and `CommandMatch` only on `Invokes`, and each of those kinds always has its value | Build |
//!
//! ## Containment tree
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | T1 | The `Workspace` node has no incoming `Contains` edge | Graph |
//! | T2 | Every other node has exactly one incoming `Contains` edge, from a parent the table allows | Graph |
//! | T3 | Following `Contains` backwards from any node reaches the `Workspace` node. There are no cycles | Graph |
//! | T4 | A node's scope agrees with its ancestors: a node in a `Project` scope sits below that project, and a node in a `Stack` scope sits below that stack | Graph |
//! | T5 | A code node below a `File` comes from that file, and so does its `Contains` parent | Graph |
//!
//! ## File record
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | F1 | No two records share project and path | Graph |
//! | F2 | Every `File` node has a record with the same project and path, and every record has a `File` node | Graph |
//! | F3 | A file whose record is not `Parsed` has a `File` node and no nodes below it | Graph |
//! | F4 | A record with `GrammarUnavailable` is read again on the next index, even when the hash is unchanged | Indexer |
//!
//! ## Unresolved reference
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | R1 | `from` is a node in the graph | Graph |
//! | R2 | `kind` is a code edge kind | Build |
//! | R3 | No two references share an id | Graph |
//! | R4 | A resolved reference is removed, and exactly one edge replaces it, with the same `from`, kind and site. Two exceptions: an `Overrides` reference whose bases all resolved, and none has the name, is removed with no edge. A reference resolved with `Flow` is kept, marked as resolved by flow, so that it can be tried again when the flow edges are rebuilt at the next index | Indexer |
//!
//! ## Call site
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | C1 | `from` is a node in the graph | Graph |
//! | C2 | Each argument has a position or a keyword, never both. Positions run from 0 without a gap | Type for "never both", Build for the gap |
//! | C3 | No two call sites share `from` and `site` | Graph |
//!
//! ## Binding
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | L1 | `in` is a `File`, `Function`, `Method` or `Class` node in the graph | Graph |
//! | L2 | `name` is not empty | Type |
//! | L3 | No two bindings share `in`, `name` and `site` | Graph |
//!
//! ## Return
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | B1 | `in` is a `Function` or `Method` node in the graph | Graph |
//! | B2 | No two returns share `in` and `site` | Graph |
//!
//! ## Inferred type
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | Y1 | `node` is a `Parameter`, `Function`, `Method`, `Field`, `Variable` or `Constant` node, and `class` is a `Class`, `Protocol` or `Enum` node | Graph |
//! | Y2 | At most one inferred type per node | Graph |
//! | Y3 | `evidence` is at least 1 | Type |
//! | Y4 | Every index removes all inferred types and every edge with `resolved_by: Flow`, and writes the ones it computed | Indexer |
//!
//! ## Reach
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | H1 | `node` is a code node in the graph. A `Binary` root is a `Binary` node; a `Module` or `Test` root is a `File` node | Graph |
//! | H2 | No two reach records share `node` and `root` | Graph |
//! | H3 | Every index removes all reach records and writes the ones it computed | Indexer |
//!
//! ## Route path
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | U1 | `route` is a `Route` node. `binary`, when given, is a `Binary` node whose framework is `Fastapi` | Graph |
//! | U2 | `complete` is true exactly when `full_path` holds no `{?}` | Type |
//! | U3 | No two route paths share `route`, `binary` and `full_path` | Graph |
//! | U4 | Every index removes all route paths and writes the ones it computed | Indexer |
//! | U5 | Every provider is a `Function`, `Method` or `Class` node | Graph |
//!
//! ## Unmatched HTTP call
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | M1 | `from` is a node in the graph, and every candidate is a `Route` node | Graph |
//! | M2 | There is never exactly one candidate: one candidate is a `Requests` edge instead | Build |
//! | M3 | Every index removes all unmatched HTTP calls and every `Requests` edge, and writes the ones it computed | Indexer |
//!
//! ## Unmatched message
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | G1 | `from` is a node in the graph, `broker` is an `ExternalService`, and every candidate is a `Topic` or `Queue` | Graph |
//! | G2 | There is never exactly one candidate | Build |
//! | G3 | Every index removes all unmatched messages and every `Sends` and `Receives` edge, and writes the ones it computed | Indexer |
//!
//! ## Message payload
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | D1 | `topic` is a `Topic` or `Queue`, `class` is a `Class`, and a `Sends` or `Receives` edge of that direction joins `node` to `topic` | Graph |
//! | D2 | No two payloads share `topic`, `node`, `direction` and `class` | Graph |
//! | D3 | Every index removes all payloads and writes the ones it computed | Indexer |
//!
//! ## Project checkout
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | P1 | There is at most one checkout per project | Graph |
//! | P2 | `project` is a `Project` node in the graph | Graph |
//! | P3 | A `branch` is given only together with a `commit` | Type |
//! | P4 | Every index writes the checkout of each project it indexes, read from the project's own `.git` folder. Nothing is fetched | Indexer |
//!
//! ## Warning
//!
//! | Id | Rule | Enforced |
//! |---|---|---|
//! | A1 | `message` is not empty | Build |
//! | A2 | A `subject`, when given, is a node in the graph | Graph |
//! | A3 | Every index replaces all stored warnings with the ones it raised | Indexer |

use std::fmt;

/// Every rule id of the domain model, including the Type and Indexer rules,
/// so that a test or a log line can name any of them.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum RuleId {
    /// `name` and `qualified_name` are not empty.
    ///
    /// Enforced by the type: `Name` and `QualifiedName` cannot be empty.
    N1,
    /// The id equals the hash of the five inputs. A node cannot be built with any other id.
    ///
    /// Enforced at build.
    N2,
    /// The scope suits the kind, as in the Scope table.
    ///
    /// Enforced at build.
    N3,
    /// A code node is always `Parsed`. `Workspace`, `Project`, `Binary`, `Topic` and `Queue` are
    /// always `Declared`. The other workspace kinds may be either.
    ///
    /// Enforced at build.
    N4,
    /// Building the same node twice from the same inputs gives the same id.
    ///
    /// Enforced at build.
    N5,
    /// No two nodes in a graph share an id.
    ///
    /// Enforced on the graph.
    N6,
    /// There is exactly one `Workspace` node.
    ///
    /// Enforced on the graph.
    N7,
    /// The data suits the kind, as in the node data table.
    ///
    /// Enforced by the type: the data is inside the `NodeKind` variant, so no other data can be
    /// there. `source` is held by `Parameter` beside its `Member`, so no other member kind can have
    /// one.
    N8,
    /// A code node's data suits the language of the file it is parsed from, and a binary's
    /// framework suits its project's language, as in the language table. The language is given when
    /// the node is built and is not stored on it.
    ///
    /// Enforced at build.
    N9,
    /// A role suits the kind, as in the role table. `app` is given only when `framework` is
    /// `Fastapi`.
    ///
    /// Enforced at build for the role, and by the type for `app`: `app` is a field of
    /// `Framework::Fastapi` and of no other variant.
    N10,
    /// A workspace edge connects only the node kinds its row allows in the workspace edge table.
    /// `Edge::new` takes the two end nodes, not their ids, so that it can check this.
    ///
    /// Enforced at build.
    E1,
    /// A workspace edge never starts and ends at the same node.
    ///
    /// Enforced at build.
    E2,
    /// The provenance suits the kind, as in the table above.
    ///
    /// Enforced at build.
    E3,
    /// `note` appears only on a `Declared` edge.
    ///
    /// Enforced by the type: `note` is a field of `Provenance::Declared` and of no other variant.
    E4,
    /// Both ends of every edge are nodes in the graph.
    ///
    /// Enforced on the graph.
    E5,
    /// No two edges share source, target, kind and site. Two calls from one function to another on
    /// different lines are two edges.
    ///
    /// Enforced on the graph.
    E6,
    /// There is at most one `DependsOn` edge from one project to another. When the manifest and the
    /// configuration both name the pair, the declared one is kept.
    ///
    /// Enforced on the graph.
    E7,
    /// A `Service` has exactly one of `Runs` or `BuiltFrom`. An `ExternalService` has neither.
    ///
    /// Enforced on the graph.
    E8,
    /// A `Binary` has exactly one `EntryPoint`, and it leads to a `File` of the same project.
    ///
    /// Enforced on the graph.
    E9,
    /// A `Runs` edge leads to a binary of the project whose folder the service is built from.
    ///
    /// Enforced on the graph.
    E10,
    /// A framework edge joins only these: `Mounts` from a `Variable` with role `App` or `Router` to
    /// such a `Variable` or to a `Route`. `Handles` from a `Route` to a `Function` or `Method`.
    /// `Injects` from a `Function`, `Method`, `Route` or `Variable` with role `Router` to a
    /// `Function`, `Method` or `Class`. `Requests` from a `Function`, `Method` or `File` to a
    /// `Route`. `Handles` may also start at a `Command`. `Sends` from a `Function`, `Method` or
    /// `File`, and `Receives` from a `Function` or `Method`, to a `Topic` or `Queue`.
    ///
    /// Enforced on the graph.
    E11,
    /// An edge with `resolved_by: Flow` rests on at least one inferred type: of a parameter of its
    /// callable, of the return of a function its receiver came from, of a field, or of a name bound
    /// more than once.
    ///
    /// Enforced on the graph.
    E12,
    /// `resolved_by` is given only on a code edge with provenance `TreeSitter` or `Scip`, and on
    /// `Invokes` (provenance `Compose` or `Dockerfile`). `Flow` is given only on `Calls` and
    /// `Instantiates`. `Framework` is given only on `Mounts`, `Handles` and `Injects`, and those
    /// three always have it. `RouteMatch` is given only on `Requests`, `MessageMatch` only on
    /// `Sends` and `Receives`, and `CommandMatch` only on `Invokes`, and each of those kinds always
    /// has its value.
    ///
    /// Enforced at build.
    E13,
    /// The `Workspace` node has no incoming `Contains` edge.
    ///
    /// Enforced on the graph.
    T1,
    /// Every other node has exactly one incoming `Contains` edge, from a parent the table allows.
    ///
    /// Enforced on the graph.
    T2,
    /// Following `Contains` backwards from any node reaches the `Workspace` node. There are no
    /// cycles.
    ///
    /// Enforced on the graph.
    T3,
    /// A node's scope agrees with its ancestors: a node in a `Project` scope sits below that
    /// project, and a node in a `Stack` scope sits below that stack.
    ///
    /// Enforced on the graph.
    T4,
    /// A code node below a `File` comes from that file, and so does its `Contains` parent.
    ///
    /// Enforced on the graph.
    T5,
    /// No two records share project and path.
    ///
    /// Enforced on the graph.
    F1,
    /// Every `File` node has a record with the same project and path, and every record has a `File`
    /// node.
    ///
    /// Enforced on the graph.
    F2,
    /// A file whose record is not `Parsed` has a `File` node and no nodes below it.
    ///
    /// Enforced on the graph.
    F3,
    /// A record with `GrammarUnavailable` is read again on the next index, even when the hash is
    /// unchanged.
    ///
    /// Enforced by the indexer.
    F4,
    /// `from` is a node in the graph.
    ///
    /// Enforced on the graph.
    R1,
    /// `kind` is a code edge kind.
    ///
    /// Enforced at build.
    R2,
    /// No two references share an id.
    ///
    /// Enforced on the graph.
    R3,
    /// A resolved reference is removed, and exactly one edge replaces it, with the same `from`,
    /// kind and site. Two exceptions: an `Overrides` reference whose bases all resolved, and none
    /// has the name, is removed with no edge. A reference resolved with `Flow` is kept, marked as
    /// resolved by flow, so that it can be tried again when the flow edges are rebuilt at the next
    /// index.
    ///
    /// Enforced by the indexer.
    R4,
    /// `from` is a node in the graph.
    ///
    /// Enforced on the graph.
    C1,
    /// Each argument has a position or a keyword, never both. Positions run from 0 without a gap.
    ///
    /// Enforced by the type for "never both": an argument's slot is `Position(u32)` or
    /// `Keyword(String)`. Enforced at build for the gap.
    C2,
    /// No two call sites share `from` and `site`.
    ///
    /// Enforced on the graph.
    C3,
    /// `in` is a `File`, `Function`, `Method` or `Class` node in the graph.
    ///
    /// Enforced on the graph.
    L1,
    /// `name` is not empty.
    ///
    /// Enforced by the type: `Name` cannot be empty.
    L2,
    /// No two bindings share `in`, `name` and `site`.
    ///
    /// Enforced on the graph.
    L3,
    /// `in` is a `Function` or `Method` node in the graph.
    ///
    /// Enforced on the graph.
    B1,
    /// No two returns share `in` and `site`.
    ///
    /// Enforced on the graph.
    B2,
    /// `node` is a `Parameter`, `Function`, `Method`, `Field`, `Variable` or `Constant` node, and
    /// `class` is a `Class`, `Protocol` or `Enum` node.
    ///
    /// Enforced on the graph.
    Y1,
    /// At most one inferred type per node.
    ///
    /// Enforced on the graph.
    Y2,
    /// `evidence` is at least 1.
    ///
    /// Enforced by the type: `evidence` is a `NonZeroU32`.
    Y3,
    /// Every index removes all inferred types and every edge with `resolved_by: Flow`, and writes
    /// the ones it computed.
    ///
    /// Enforced by the indexer.
    Y4,
    /// `node` is a code node in the graph. A `Binary` root is a `Binary` node; a `Module` or `Test`
    /// root is a `File` node.
    ///
    /// Enforced on the graph.
    H1,
    /// No two reach records share `node` and `root`.
    ///
    /// Enforced on the graph.
    H2,
    /// Every index removes all reach records and writes the ones it computed.
    ///
    /// Enforced by the indexer.
    H3,
    /// `route` is a `Route` node. `binary`, when given, is a `Binary` node whose framework is
    /// `Fastapi`.
    ///
    /// Enforced on the graph.
    U1,
    /// `complete` is true exactly when `full_path` holds no `{?}`.
    ///
    /// Enforced by the type: `complete` is not stored. `RoutePath::is_complete()` works it out from
    /// `full_path`.
    U2,
    /// No two route paths share `route`, `binary` and `full_path`.
    ///
    /// Enforced on the graph.
    U3,
    /// Every index removes all route paths and writes the ones it computed.
    ///
    /// Enforced by the indexer.
    U4,
    /// Every provider is a `Function`, `Method` or `Class` node.
    ///
    /// Enforced on the graph.
    U5,
    /// `from` is a node in the graph, and every candidate is a `Route` node.
    ///
    /// Enforced on the graph.
    M1,
    /// There is never exactly one candidate: one candidate is a `Requests` edge instead.
    ///
    /// Enforced at build.
    M2,
    /// Every index removes all unmatched HTTP calls and every `Requests` edge, and writes the ones
    /// it computed.
    ///
    /// Enforced by the indexer.
    M3,
    /// `from` is a node in the graph, `broker` is an `ExternalService`, and every candidate is a
    /// `Topic` or `Queue`.
    ///
    /// Enforced on the graph.
    G1,
    /// There is never exactly one candidate.
    ///
    /// Enforced at build.
    G2,
    /// Every index removes all unmatched messages and every `Sends` and `Receives` edge, and writes
    /// the ones it computed.
    ///
    /// Enforced by the indexer.
    G3,
    /// `topic` is a `Topic` or `Queue`, `class` is a `Class`, and a `Sends` or `Receives` edge of
    /// that direction joins `node` to `topic`.
    ///
    /// Enforced on the graph.
    D1,
    /// No two payloads share `topic`, `node`, `direction` and `class`.
    ///
    /// Enforced on the graph.
    D2,
    /// Every index removes all payloads and writes the ones it computed.
    ///
    /// Enforced by the indexer.
    D3,
    /// There is at most one checkout per project.
    ///
    /// Enforced on the graph.
    P1,
    /// `project` is a `Project` node in the graph.
    ///
    /// Enforced on the graph.
    P2,
    /// A `branch` is given only together with a `commit`.
    ///
    /// Enforced by the type: `commit` and `branch` sit together in `Head { commit: CommitId,
    /// branch: Option<String> }`, and a checkout holds `head: Option<Head>`.
    P3,
    /// Every index writes the checkout of each project it indexes, read from the project's own
    /// `.git` folder. Nothing is fetched.
    ///
    /// Enforced by the indexer.
    P4,
    /// `message` is not empty.
    ///
    /// Enforced at build.
    A1,
    /// A `subject`, when given, is a node in the graph.
    ///
    /// Enforced on the graph.
    A2,
    /// Every index replaces all stored warnings with the ones it raised.
    ///
    /// Enforced by the indexer.
    A3,
}

impl RuleId {
    /// The id as written in `docs/domain-model.md`, such as `"N1"`.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::N1 => "N1",
            Self::N2 => "N2",
            Self::N3 => "N3",
            Self::N4 => "N4",
            Self::N5 => "N5",
            Self::N6 => "N6",
            Self::N7 => "N7",
            Self::N8 => "N8",
            Self::N9 => "N9",
            Self::N10 => "N10",
            Self::E1 => "E1",
            Self::E2 => "E2",
            Self::E3 => "E3",
            Self::E4 => "E4",
            Self::E5 => "E5",
            Self::E6 => "E6",
            Self::E7 => "E7",
            Self::E8 => "E8",
            Self::E9 => "E9",
            Self::E10 => "E10",
            Self::E11 => "E11",
            Self::E12 => "E12",
            Self::E13 => "E13",
            Self::T1 => "T1",
            Self::T2 => "T2",
            Self::T3 => "T3",
            Self::T4 => "T4",
            Self::T5 => "T5",
            Self::F1 => "F1",
            Self::F2 => "F2",
            Self::F3 => "F3",
            Self::F4 => "F4",
            Self::R1 => "R1",
            Self::R2 => "R2",
            Self::R3 => "R3",
            Self::R4 => "R4",
            Self::C1 => "C1",
            Self::C2 => "C2",
            Self::C3 => "C3",
            Self::L1 => "L1",
            Self::L2 => "L2",
            Self::L3 => "L3",
            Self::B1 => "B1",
            Self::B2 => "B2",
            Self::Y1 => "Y1",
            Self::Y2 => "Y2",
            Self::Y3 => "Y3",
            Self::Y4 => "Y4",
            Self::H1 => "H1",
            Self::H2 => "H2",
            Self::H3 => "H3",
            Self::U1 => "U1",
            Self::U2 => "U2",
            Self::U3 => "U3",
            Self::U4 => "U4",
            Self::U5 => "U5",
            Self::M1 => "M1",
            Self::M2 => "M2",
            Self::M3 => "M3",
            Self::G1 => "G1",
            Self::G2 => "G2",
            Self::G3 => "G3",
            Self::D1 => "D1",
            Self::D2 => "D2",
            Self::D3 => "D3",
            Self::P1 => "P1",
            Self::P2 => "P2",
            Self::P3 => "P3",
            Self::P4 => "P4",
            Self::A1 => "A1",
            Self::A2 => "A2",
            Self::A3 => "A3",
        }
    }
}

impl fmt::Display for RuleId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::RuleId;

    #[test]
    fn rule_ids_print_as_written_in_the_model() {
        assert_eq!(RuleId::N10.to_string(), "N10");
        assert_eq!(RuleId::E13.to_string(), "E13");
    }
}
