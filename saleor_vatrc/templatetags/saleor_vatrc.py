"""Custom tags for various VAT-related utilities."""
from django import template
from django_countries.fields import Country

from saleor.plugins.manager import get_plugins_manager
import saleor_vatrc.plugin

register = template.Library()


def _get_vat_plugin():
    vat_plugin_id = saleor_vatrc.plugin.VatReverseCharge.VAT_PLUGIN_ID
    manager = get_plugins_manager()
    plugins = manager.all_plugins
    vat_plugin = next(
        (
            p for p in plugins
            if p.PLUGIN_ID == vat_plugin_id),
        None
    )
    return vat_plugin


@register.simple_tag(takes_context=True)
def get_value_from_metadata(context, obj, key: str) -> bool:
    """Retrieve a value from object's metadata."""
    return obj.get_value_from_metadata(key)


@register.simple_tag(takes_context=True)
def taxes_for_country(context, country_code):
    """Retrieve taxes for a given country."""
    country = Country(country_code)
    vat_plugin = _get_vat_plugin()
    return vat_plugin._get_taxes_for_country(country)


@register.simple_tag(takes_context=True)
def is_vatrc_applicable(context, order) -> bool:
    """Return True if reverse charged VAT is applicable to a given order."""
    vatin_key = saleor_vatrc.plugin.VatReverseCharge.META_VATIN_VALIDATED_KEY
    vatin = order.get_value_from_metadata(vatin_key)
    if not vatin:
        return False
    vat_plugin = _get_vat_plugin()
    billing_country = order.billing_address.country
    if not vat_plugin._get_taxes_for_country(billing_country):
        return False
    if billing_country.code == Country(vat_plugin.config.origin_country):
        return False
    return True


@register.simple_tag(takes_context=True)
def is_vat_applicable(context, order):
    """Return True if VAT is applicable to a given order."""
    vat_plugin = _get_vat_plugin()
    billing_country = order.billing_address.country
    if not vat_plugin._get_taxes_for_country(billing_country):
        return False
    return True
