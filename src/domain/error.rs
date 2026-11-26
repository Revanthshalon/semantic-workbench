//! The errors a domain value gives when it is refused.

use crate::domain::rule::RuleId;

/// The value type a malformed input was meant to become.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValueKind {
    /// A `ProjectId`.
    ProjectId,
    /// A `ComposeName`.
    ComposeName,
    /// A `RelPath`.
    RelPath,
    /// A `ContentHash`.
    ContentHash,
    /// A `NodeId`.
    NodeId,
    /// A `ReferenceId`.
    ReferenceId,
    /// A `Name`.
    Name,
    /// A `QualifiedName`.
    QualifiedName,
    /// A `CommitId`.
    CommitId,
    /// A `Line`.
    Line,
    /// A `Span`.
    Span,
}

/// The reason a domain value was refused.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum DomainError {
    /// Text that does not have the form of its value type.
    #[error("not a valid {value:?}: {input:?}: {reason}")]
    Malformed {
        /// The value type the input was meant to become.
        value: ValueKind,
        /// The text that was refused.
        input: String,
        /// Why the text was refused.
        reason: &'static str,
    },
    /// A value that breaks a rule of the domain model.
    #[error("rule {rule}: {message}")]
    Rule {
        /// The rule that was broken.
        rule: RuleId,
        /// What was wrong with the value.
        message: String,
    },
}

#[cfg(test)]
mod tests {
    use super::DomainError;
    use crate::domain::rule::RuleId;

    #[test]
    fn rule_error_names_its_rule() {
        let error = DomainError::Rule {
            rule: RuleId::N3,
            message: String::from("the scope does not suit the kind"),
        };
        assert!(error.to_string().starts_with("rule N3:"));
    }
}
