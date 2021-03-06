from dataclasses import dataclass, field
from functools import lru_cache
from os import getenv
from typing import Any, Dict, List, Union

from pymanifold import ManifoldClient
from pymanifold.types import DictDeserializable, Market as APIMarket

from .rule import DoResolveRule, ResolutionValueRule


@lru_cache
def get_client() -> ManifoldClient:
    return ManifoldClient(getenv("ManifoldAPIKey"))


@dataclass
class Market(DictDeserializable):
    market: APIMarket
    client: ManifoldClient = field(default_factory=get_client)
    notes: str = field(default='')
    do_resolve_rules: List[DoResolveRule] = field(default_factory=list)
    resolve_to_rules: List[ResolutionValueRule] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market": self.market,
            "notes": self.notes,
            "do_resolve_rules": self.do_resolve_rules,
            "resolve_to_rules": self.resolve_to_rules,
        }

    @property
    def id(self):
        return self.market.id

    @classmethod
    def from_slug(cls, slug: str, *args, **kwargs):
        api_market = get_client().get_market_by_slug(slug)
        return cls(api_market, *args, **kwargs)

    @classmethod
    def from_id(cls, id: str, *args, **kwargs):
        api_market = get_client().get_market_by_id(id)
        return cls(api_market, *args, **kwargs)

    def should_resolve(self) -> bool:
        return any(
            rule.value(self) for rule in (self.do_resolve_rules or ())
        ) and not self.market.isResolved

    def resolve_to(self) -> Union[int, float, Dict[int, float], str]:
        """Select a value to be resolved to.

        This is done by iterating through a series of Rules, each of which have
        opportunity to recommend a value. The first resolved value is resolved to.

        Binary markets must return a float between 0 and 100.
        Numeric markets must return a float in its correct range.
        Free response markets must resolve to either a single index integer or
         a mapping of indices to weights.
        Any rule may return "CANCEL" to instead refund all orders.
        """
        chosen = None
        for rule in (self.resolve_to_rules or ()):
            if (chosen := rule.value(self)) is not None:
                break
        if chosen is not None:
            return chosen
        if self.market.probability is not None:
            return bool(round(self.market.probability))
        return max(self.market.answers, key=lambda x: x['probability'])

    def resolve(self):
        """Resolves this market according to our resolution rules.

        Returns
        -------
        Response
            How Manifold interprets our request, and some JSON data on it
        """
        return self.client.resolve_market(self.market, self.resolve_to())
