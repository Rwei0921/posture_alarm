# Task: one-time LINE group ID setup utility

Implement a one-time LINE group ID setup utility for this posture_alarm project.

## Context

- The existing application already sends LINE Messaging API push messages using LINE_CHANNEL_ACCESS_TOKEN and LINE_TARGET_ID.
- I want alerts sent to one LINE group so multiple people can receive them.
- The channel's Webhook URL is currently blank.
- The existing GUI, embedded camera/ROI tab, Raspberry Pi startup configuration, fall detection, GPIO, sensors, notifications, database, and cooldown behavior must remain unchanged.

First read AGENTS.md and inspect the existing configuration, LINE notifier, environment-file helpers, and relevant tests. Explain the implementation plan before editing. Keep the changes narrowly scoped.

## 1. Standalone setup utility

Prefer a top-level setup_line_group.py script, with a small helper module only if needed.

The intended Raspberry Pi command is:

```bash
.venv/bin/python setup_line_group.py
```

Requirements:

- Use the existing virtual environment and Python standard library where practical.
- Do not add Flask, FastAPI, or other large dependencies.
- Read demo.env using the project's existing safe parser. Do not execute or source the file.
- Keep environment-variable parsing centralized in config.py.
- Add LINE_CHANNEL_SECRET only where necessary, including a blank placeholder in the environment example.
- Keep the channel secret local. Never print it, put it in command-line arguments, or request that I paste it into the conversation.
- If the secret is missing, provide a clear configuration instruction or use a hidden local terminal prompt.
- Use English console messages to avoid terminal encoding issues. Follow project rules for Traditional Chinese comments on important logic.

## 2. Webhook receiver

- Bind only to 127.0.0.1, with a configurable port and a sensible default.
- Expose one documented webhook path, such as /line/webhook.
- Do not bind to 0.0.0.0 or expose the existing GUI, camera, project files, or other application services.
- Verify X-Line-Signature using HMAC-SHA256 and the channel secret.
- Calculate the signature from the exact raw request body before parsing JSON.
- Use a constant-time signature comparison.
- Reject missing, invalid, or tampered signatures.
- Add reasonable request-body limits, read timeouts, and validation for malformed requests.
- Return HTTP 200 for a correctly signed LINE verification request containing an empty events array. This must not count as successful group pairing.

## 3. Explicit group pairing

- Generate a random, one-time pairing phrase at startup and display it locally.
- Instruct the user to send that exact phrase in the intended LINE group after inviting the official account.
- Accept a group ID only from a correctly signed group text-message event whose text matches the pairing phrase.
- Validate the group ID format.
- Ignore unrelated messages, private chats, room events, and incorrect pairing phrases.
- Do not print or persist complete webhook payloads, chat histories, user IDs, reply tokens, secrets, or unrelated message text.
- After successful pairing, respond to LINE, display the group ID locally, and shut down cleanly.
- Handle duplicate deliveries and Ctrl+C safely.
- Do not automatically overwrite LINE_TARGET_ID. The user will copy the group ID into the existing GUI.
- Do not automatically send replies or test notifications.

## 4. Temporary public HTTPS connection

LINE needs to reach the webhook through a public HTTPS URL.

- Verify current LINE requirements and suitable temporary HTTPS-tunnel instructions using official documentation.
- Document how the user can temporarily forward HTTPS traffic to this localhost-only setup receiver.
- Do not automatically install software, start a tunnel, publish an endpoint, change firewall/router settings, or configure the user's LINE account.
- If an additional tunnel executable is required, explain why and provide verified manual installation instructions appropriate for Raspberry Pi OS and its CPU architecture.
- Do not require a permanent server or permanently enabled webhook.

## 5. Beginner-friendly documentation

Add line_group_setup.md covering:

- Enabling "Allow bot to join group chats".
- Creating the alert group and inviting the official account.
- Finding the Channel secret in Basic settings.
- The difference between Channel secret, Channel access token, personal userId, and groupId.
- Starting the setup utility and temporary HTTPS tunnel.
- Entering the correct public HTTPS webhook URL and enabling Use webhook.
- Running LINE's webhook verification.
- Sending the generated pairing phrase in the intended group.
- Copying the resulting group ID into the GUI's LINE Target ID field.
- Manually sending a LINE test notification from the GUI.
- Saving the configuration and restarting monitoring when necessary.
- Disabling Use webhook and stopping the temporary tunnel after setup.
- Explaining that normal outbound push notifications can continue using the saved group ID without keeping this setup receiver running.
- Troubleshooting invalid signatures, wrong paths, unreachable URLs, incorrect secrets, and accidentally selecting the wrong group.
- Using a test group without sensitive conversation content during setup.

## 6. Tests and verification

Add offline tests for:

- Correct, missing, invalid, and tampered signatures.
- Empty-events verification requests.
- Correct group pairing.
- Wrong pairing phrases and non-group events.
- Invalid group IDs.
- Duplicate events.
- Malformed JSON and oversized requests.
- Safe output that does not disclose credentials or full message contents.
- Clean shutdown and resource cleanup.

Tests must not contact LINE, send notifications, open tunnels, access real camera/GPIO, or require a GUI.

Run the focused tests, the project's import-health check, the full pytest suite, and git diff --check. Use the existing virtual environment. Clearly distinguish automated tests from untested real LINE/Raspberry Pi integration.

## Final report

- List changed files and explain their purpose.
- Provide exact Raspberry Pi commands and the required manual LINE Console steps.
- Report actual test results and remaining manual checks.

## Do not

- Change fall-classification formulas, state transitions, ROI behavior, notification cooldowns, or hardware pins.
- Change existing LINE notifier interfaces or GUI workflows unnecessarily.
- Modify startup services or reboot the Raspberry Pi.
- Upgrade dependencies, downgrade Python, or perform unrelated refactoring.
- Commit demo.env, tokens, channel secrets, or captured webhook data.
- Commit or push anything unless I explicitly request it afterward.
