"""AWS SSM Parameter Store helpers."""

from functools import lru_cache

import boto3


@lru_cache
def _ssm_client():
    return boto3.client("ssm")


def get_parameter(name: str, *, with_decryption: bool = True) -> str:
    """Fetch a parameter value from SSM Parameter Store."""
    response = _ssm_client().get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]
