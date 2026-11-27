//! Workbench reads a workspace of several projects and stores what it finds as a graph: the
//! code inside each project, the projects themselves, the services that run them, and the
//! links between all of these. People and AI tools query the graph through the command line.

#![allow(dead_code)]

use std::process::ExitCode;

mod adapters;
mod config;
mod domain;
mod ports;
mod use_cases;

/// Runs `workbench` and returns its exit status.
pub fn main() -> ExitCode {
    ExitCode::SUCCESS
}
