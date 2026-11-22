#![allow(missing_docs)]

use std::process::ExitCode;

mod adapters;
mod config;
mod domain;
mod ports;
mod use_cases;

pub fn main() -> ExitCode {
    ExitCode::SUCCESS
}
