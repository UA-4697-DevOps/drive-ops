# run-script-via-ssm

Composite action that runs a base64-encoded script on an EC2 instance through the shared SSM action.

## Inputs

- `instance-id` (required): EC2 instance ID.
- `script-b64` (required): Base64-encoded script content.
- `script-name` (optional): Script filename on the instance. Default: `script.sh`.
- `env-vars` (optional): Trusted multi-line environment assignments loaded before script execution.
- `working-directory` (optional): Remote working directory. Default: `/home/ubuntu`.
- `timeout-seconds` (optional): Command timeout. Default: `300`.

## Security Notes

`env-vars` must only contain trusted, simple `VAR=VALUE` assignments, one per line.

Allowed format:

- Variable name: `^[A-Z_][A-Z0-9_]*$`
- Entire line: `^[A-Z_][A-Z0-9_]*=[A-Za-z0-9_./:@%+=,-]*$`

Do not pass shell commands, command substitutions, or untrusted user input through `env-vars`.
