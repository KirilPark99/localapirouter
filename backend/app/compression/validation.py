"""Strict validation shared by admin writes and runtime overrides."""
import json
import math
from app.core.safe_regex import validate_pattern


def validate_globals(data):
    bounds = {'trigger_token_threshold': (0, 10000000), 'preserve_recent_turns': (0, 1000),
              'min_savings_bailout_percent': (0, 100)}
    allowed = set(bounds) | {'enabled', 'enable_telemetry', 'fail_open', 'preserve_system_prompt_mode'}
    for key, value in data.items():
        if key not in allowed or value is None:
            raise ValueError(f'Invalid global setting: {key}')
        if key in bounds:
            low, high = bounds[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{key} must be between {low} and {high}')
            if key != 'min_savings_bailout_percent' and not isinstance(value, int):
                raise ValueError(f'{key} must be an integer')
        elif key == 'preserve_system_prompt_mode':
            if value not in {'always', 'never', 'when_caching'}:
                raise ValueError('Invalid system preservation mode')
        elif type(value) is not bool:
            raise ValueError(f'{key} must be a boolean')


def validate_rules(rules):
    if isinstance(rules, str):
        try:
            rules = json.loads(rules)
        except (ValueError, TypeError) as exc:
            raise ValueError('rules must be a JSON array') from exc
    if not isinstance(rules, list) or len(rules) > 50:
        raise ValueError('rules must be a list of at most 50 rules')
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {'pattern', 'replacement', 'case_sensitive'}:
            raise ValueError('Invalid regex rule')
        if not isinstance(rule.get('pattern'), str) or not isinstance(rule.get('replacement', ''), str):
            raise ValueError('Pattern and replacement must be strings')
        if len(rule.get('replacement', '')) > 4096 or type(rule.get('case_sensitive', False)) is not bool:
            raise ValueError('Invalid replacement or case_sensitive')
        validate_pattern(rule['pattern'])
    return rules


def validate_stage_config(stage, config):
    if stage is None or not isinstance(config, dict):
        raise ValueError('Invalid stage/configuration')
    fields = {field.key: field for field in stage.get_config_schema()}
    for key, value in config.items():
        if key not in fields or value is None:
            raise ValueError(f'Unknown or null stage setting: {key}')
        field = fields[key]
        if key == 'rules':
            validate_rules(value)
        elif field.type == 'boolean':
            if type(value) is not bool:
                raise ValueError(f'{key} must be a boolean')
        elif field.type == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{key} must be a finite number')
            if isinstance(field.default_value, int) and not isinstance(value, int):
                raise ValueError(f'{key} must be an integer')
            if field.min_value is not None and value < field.min_value or field.max_value is not None and value > field.max_value:
                raise ValueError(f'{key} is out of bounds')
        elif field.type == 'select':
            if value not in {option['value'] for option in field.options or []}:
                raise ValueError(f'Invalid {key} mode')
        elif not isinstance(value, str) or len(value) > 65536:
            raise ValueError(f'{key} must be a bounded string')
