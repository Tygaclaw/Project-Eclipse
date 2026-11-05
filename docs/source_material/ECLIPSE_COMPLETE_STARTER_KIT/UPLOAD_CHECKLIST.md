# New Chat Upload Checklist

## Preferred method

Upload the whole `ECLIPSE_COMPLETE_STARTER_KIT.zip` archive to a new ChatGPT conversation. The original five sources and the updated instructions are all inside. Then send:

`GO`

## If ZIP upload or reading fails

Upload these seven files individually:

1. `START_HERE.md`
2. `MASTER_EXECUTION_PROMPT.md`
3. `SOURCE_DOCUMENTS/01_HISTORICAL_CLAUDE_START_HERE_SUPERSEDED.md`
4. `SOURCE_DOCUMENTS/02_ECLIPSE_Unified_Implementation_Handoff_ORIGINAL.md`
5. `SOURCE_DOCUMENTS/03_ECLIPSE_Continuation_Ledger_ORIGINAL.md`
6. `SOURCE_DOCUMENTS/04_ECLIPSE_Full_Up_to_Date_Master_Plan_Styled_ORIGINAL.pdf`
7. `SOURCE_DOCUMENTS/05_Original_Qwen_Capability_Amplification_Discussion_ORIGINAL.txt`

(The first two are current instructions; the remaining five are the original sources. That's seven individual files in the fallback method.)

Then send `GO`.

## Before sending

- Use a fresh conversation so the handoff is clear.
- Ensure the GitHub connector is connected to the account containing the ECLIPSE repositories.
- Do not include API-key values or private model files.
- The old historical repository must remain untouched.

## What should happen

ChatGPT should read the package, verify GitHub access, establish a separate private repository and begin implementation. It should not ask you to repeat the completed machine audit, reinstall Qwen, recreate API secrets or repeat A* as a prerequisite.
