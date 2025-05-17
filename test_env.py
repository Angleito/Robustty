import os
from dotenv import load_dotenv

load_dotenv()

print(f"RUMBLE_ENABLED: {os.getenv('RUMBLE_ENABLED')}")
print(f"RUMBLE_API_TOKEN: {os.getenv('RUMBLE_API_TOKEN')}")

# Simulate what the config loader is doing
rumble_enabled = os.getenv('RUMBLE_ENABLED', 'false')
print(f"Parsed RUMBLE_ENABLED: {rumble_enabled}")
print(f"Type: {type(rumble_enabled)}")
print(f"Bool value: {rumble_enabled.lower() not in ['false', '0', 'no']}")

# Test YAML parsing
import yaml
yaml_str = "enabled: ${RUMBLE_ENABLED:false}"
yaml_str_replaced = yaml_str.replace("${RUMBLE_ENABLED:false}", rumble_enabled)
print(f"YAML string: {yaml_str_replaced}")
parsed = yaml.safe_load(yaml_str_replaced)
print(f"Parsed YAML: {parsed}")
print(f"Type of enabled: {type(parsed['enabled'])}")