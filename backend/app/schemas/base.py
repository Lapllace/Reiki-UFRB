"""Configuração comum dos schemas: camelCase na API, snake_case em Python."""

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=None, populate_by_name=True, from_attributes=True)


def camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(w.title() for w in rest)
