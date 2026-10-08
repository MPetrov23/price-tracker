from bs4 import BeautifulSoup

from StrollerPriceTracker import _to_float
from StrollerPriceTracker import extract_price_jsonld

def test_to_float_with_comma():
    assert _to_float("515,90 лв.") == 515.90


def test_to_float_with_dot():
    assert _to_float("515.90") == 515.90


def test_to_float_with_integer():
    assert _to_float("515 лв.") == 515.0


def test_to_float_with_invalid_value():
    assert _to_float("няма цена") is None


def test_extract_price_jsonld():
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Lionelo Mika Plus",
                "offers": {
                    "@type": "Offer",
                    "price": "599.90",
                    "priceCurrency": "BGN"
                }
            }
            </script>
        </head>
    </html>
    """

    soup = BeautifulSoup(html, "lxml")

    assert extract_price_jsonld(soup) == 599.90


def test_extract_price_jsonld_without_price():
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Lionelo Mika Plus"
            }
            </script>
        </head>
    </html>
    """

    soup = BeautifulSoup(html, "lxml")

    assert extract_price_jsonld(soup) is None