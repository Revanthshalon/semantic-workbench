//! The stores that keep the graph. Each backend sits behind its own feature.

#[cfg(feature = "memgraph")]
pub mod memgraph;

#[cfg(feature = "sqlite")]
pub mod sqlite;
