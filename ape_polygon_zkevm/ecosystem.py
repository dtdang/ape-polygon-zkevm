from typing import Optional, Type, Union, cast

from ape.api import TransactionAPI
from ape.api.config import PluginConfig
from ape.api.networks import LOCAL_NETWORK_NAME
from ape.exceptions import ApeException
from ape.types import TransactionSignature
from ape_ethereum.ecosystem import Ethereum, NetworkConfig
from ape_ethereum.transactions import StaticFeeTransaction, TransactionType
from eth_typing import HexStr
from eth_utils import add_0x_prefix

NETWORKS = {
    # chain_id, network_id
    "mainnet": (1101, 1101),
    "goerli": (1442, 1442),
}


class ApePolygonZkEVMError(ApeException):
    """
    Raised in the ape-polygon-zkevm plugin.
    """


def _create_network_config(
    required_confirmations: int = 1, block_time: int = 2, **kwargs
) -> NetworkConfig:
    return NetworkConfig(
        required_confirmations=required_confirmations, block_time=block_time, **kwargs
    )


def _create_local_config(default_provider: Optional[str] = None) -> NetworkConfig:
    return _create_network_config(
        required_confirmations=0, block_time=0, default_provider=default_provider
    )


class PolygonZkEVMConfig(PluginConfig):
    mainnet: NetworkConfig = _create_network_config()
    mainnet_fork: NetworkConfig = _create_local_config()
    goerli: NetworkConfig = _create_network_config()
    goerli_fork: NetworkConfig = _create_local_config()
    local: NetworkConfig = _create_local_config(default_provider="test")
    default_network: str = LOCAL_NETWORK_NAME


class PolygonZkEVM(Ethereum):
    @property
    def config(self) -> PolygonZkEVMConfig:  # type: ignore
        return cast(PolygonZkEVMConfig, self.config_manager.get_config("polygonzk"))

    def create_transaction(self, **kwargs) -> TransactionAPI:
        """
        Returns a transaction using the given constructor kwargs.
        Overridden because does not support

        **kwargs: Kwargs for the transaction class.

        Returns:
            :class:`~ape.api.transactions.TransactionAPI`
        """

        transaction_type = _get_transaction_type(kwargs.get("type"))
        kwargs["type"] = transaction_type.value
        txn_class = _get_transaction_cls(transaction_type)

        if "required_confirmations" not in kwargs or kwargs["required_confirmations"] is None:
            # Attempt to use default required-confirmations from `ape-config.yaml`.
            required_confirmations = 0
            active_provider = self.network_manager.active_provider
            if active_provider:
                required_confirmations = active_provider.network.required_confirmations

            kwargs["required_confirmations"] = required_confirmations

        if isinstance(kwargs.get("chainId"), str):
            kwargs["chainId"] = int(kwargs["chainId"], 16)

        if "hash" in kwargs:
            kwargs["data"] = kwargs.pop("hash")

        if all(field in kwargs for field in ("v", "r", "s")):
            kwargs["signature"] = TransactionSignature(
                v=kwargs["v"],
                r=bytes(kwargs["r"]),
                s=bytes(kwargs["s"]),
            )

        return txn_class.parse_obj(kwargs)


def _get_transaction_type(_type: Optional[Union[int, str, bytes]]) -> TransactionType:
    if not _type:
        return TransactionType.STATIC

    if _type is None:
        _type = TransactionType.STATIC.value
    elif isinstance(_type, int):
        _type = f"0{_type}"
    elif isinstance(_type, bytes):
        _type = _type.hex()

    suffix = _type.replace("0x", "")
    if len(suffix) == 1:
        _type = f"{_type.rstrip(suffix)}0{suffix}"

    return TransactionType(add_0x_prefix(HexStr(_type)))


def _get_transaction_cls(transaction_type: TransactionType) -> Type[TransactionAPI]:
    transaction_types = {
        TransactionType.STATIC: StaticFeeTransaction,
    }
    if transaction_type not in transaction_types:
        raise ApePolygonZkEVMError(f"Transaction type '{transaction_type}' not supported.")

    return transaction_types[transaction_type]