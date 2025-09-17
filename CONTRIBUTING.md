# Contributing

Thanks for your interest in improving AMP Auto Shutdown! This document summarises how to report issues, propose changes, and submit pull requests.

## Getting Started
1. Fork the repository and clone it locally.
2. Install Python 3.11 or later.
3. Create and activate a virtual environment, then install dependencies:
   `powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .[dev]
   `
4. Run the test suite to confirm everything is green:
   `powershell
   pytest
   `

## Development Workflow
- Create a feature branch from main using a descriptive name.
- Follow the existing code style; formatters such as uff or lack are welcome but not enforced.
- Keep functions focused and add concise comments only where the logic is non-obvious.
- Update or add tests for new behaviour. Tests should run via pytest without external services.
- Update documentation (README, changelog) when you add user-visible changes.

## Pull Requests
- Reference related issues in your PR description.
- Summarise what changed, why it changed, and how you tested it.
- Ensure pytest passes on Windows; GitHub Actions will verify.
- New features should include entries in CHANGELOG.md under the **Unreleased** section.

## Reporting Issues
When filing an issue, include:
- Windows version (e.g. Windows 11 23H2)
- AMP version and instance types
- Steps to reproduce and expected vs actual results
- Relevant log excerpts from %ProgramData%\AmpAutoShutdown\logs\amp_autoshutdown.log

## Code of Conduct
Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before engaging with the community.
