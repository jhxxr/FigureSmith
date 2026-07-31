"""Bounded SVG sanitization shared by generation and artifact egress."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from figuresmith.models.errors import UnsafeSvgContent

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"


@dataclass(frozen=True)
class SvgLimits:
    max_bytes: int = 8 * 1024 * 1024
    max_elements: int = 20_000
    max_depth: int = 128
    max_attributes: int = 128
    max_attribute_length: int = 256 * 1024
    max_data_uri_bytes: int = 4 * 1024 * 1024


@dataclass(frozen=True)
class SanitizedSvg:
    data: bytes

    def __bytes__(self) -> bytes:
        return self.data


_ALLOWED_ELEMENTS = frozenset(
    {
        "svg",
        "g",
        "defs",
        "desc",
        "title",
        "metadata",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "path",
        "text",
        "tspan",
        "use",
        "symbol",
        "marker",
        "clipPath",
        "mask",
        "linearGradient",
        "radialGradient",
        "stop",
        "pattern",
        "image",
        "filter",
        "feGaussianBlur",
        "feColorMatrix",
        "feOffset",
        "feBlend",
        "feComposite",
        "feFlood",
        "feMerge",
        "feMergeNode",
        "feMorphology",
        "feComponentTransfer",
        "feFuncA",
        "feFuncR",
        "feFuncG",
        "feFuncB",
    }
)

_GLOBAL_ATTRIBUTES = frozenset(
    {
        "id",
        "class",
        "role",
        "aria-label",
        "style",
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "opacity",
        "transform",
        "display",
        "visibility",
        "clip-path",
        "clip-rule",
        "mask",
        "filter",
        "marker-start",
        "marker-mid",
        "marker-end",
        "vector-effect",
        "color",
        "color-interpolation",
        "color-interpolation-filters",
        "font-family",
        "font-size",
        "font-weight",
        "font-style",
        "letter-spacing",
        "text-anchor",
        "text-decoration",
        "dominant-baseline",
        "alignment-baseline",
        "shape-rendering",
        "text-rendering",
        "image-rendering",
        "writing-mode",
        "direction",
        "unicode-bidi",
        "enable-background",
        "result",
        "in",
        "in2",
        "mode",
        "operator",
        "type",
        "values",
        "value",
        "kernelMatrix",
        "stdDeviation",
        "flood-color",
        "flood-opacity",
        "tableValues",
        "slope",
        "intercept",
        "amplitude",
        "exponent",
        "xChannelSelector",
        "yChannelSelector",
        "k1",
        "k2",
        "k3",
        "k4",
    }
)

_ELEMENT_ATTRIBUTES: dict[str, frozenset[str]] = {
    "svg": frozenset(
        {
            "xmlns",
            "xmlns:xlink",
            "version",
            "viewBox",
            "width",
            "height",
            "x",
            "y",
            "preserveAspectRatio",
        }
    ),
    "image": frozenset({"x", "y", "width", "height", "preserveAspectRatio"}),
    "rect": frozenset({"x", "y", "width", "height", "rx", "ry"}),
    "circle": frozenset({"cx", "cy", "r"}),
    "ellipse": frozenset({"cx", "cy", "rx", "ry"}),
    "line": frozenset({"x1", "y1", "x2", "y2"}),
    "polyline": frozenset({"points"}),
    "polygon": frozenset({"points"}),
    "path": frozenset({"d"}),
    "text": frozenset({"x", "y", "dx", "dy", "textLength", "lengthAdjust"}),
    "tspan": frozenset({"x", "y", "dx", "dy", "textLength", "lengthAdjust"}),
    "use": frozenset({"x", "y", "width", "height"}),
    "symbol": frozenset({"viewBox", "preserveAspectRatio"}),
    "marker": frozenset(
        {
            "markerWidth",
            "markerHeight",
            "refX",
            "refY",
            "orient",
            "viewBox",
            "preserveAspectRatio",
        }
    ),
    "clipPath": frozenset({"clipPathUnits"}),
    "mask": frozenset({"x", "y", "width", "height", "maskUnits", "maskContentUnits"}),
    "linearGradient": frozenset(
        {"x1", "y1", "x2", "y2", "gradientUnits", "gradientTransform", "spreadMethod"}
    ),
    "radialGradient": frozenset(
        {"cx", "cy", "r", "fx", "fy", "fr", "gradientUnits", "gradientTransform", "spreadMethod"}
    ),
    "stop": frozenset({"offset", "stop-color", "stop-opacity"}),
    "pattern": frozenset(
        {
            "x",
            "y",
            "width",
            "height",
            "patternUnits",
            "patternContentUnits",
            "patternTransform",
            "viewBox",
            "preserveAspectRatio",
        }
    ),
    "filter": frozenset({"x", "y", "width", "height", "filterUnits", "primitiveUnits"}),
    "feGaussianBlur": frozenset({"stdDeviation", "edgeMode"}),
    "feColorMatrix": frozenset({"values", "type"}),
    "feOffset": frozenset({"dx", "dy"}),
    "feBlend": frozenset({"in", "in2", "mode"}),
    "feComposite": frozenset({"in", "in2", "operator", "k1", "k2", "k3", "k4"}),
    "feFlood": frozenset({"flood-color", "flood-opacity"}),
    "feMergeNode": frozenset({"in"}),
    "feMorphology": frozenset({"in", "operator", "radius"}),
    "feComponentTransfer": frozenset({"in"}),
    "feFuncA": frozenset(
        {"type", "tableValues", "slope", "intercept", "amplitude", "exponent", "offset"}
    ),
    "feFuncR": frozenset(
        {"type", "tableValues", "slope", "intercept", "amplitude", "exponent", "offset"}
    ),
    "feFuncG": frozenset(
        {"type", "tableValues", "slope", "intercept", "amplitude", "exponent", "offset"}
    ),
    "feFuncB": frozenset(
        {"type", "tableValues", "slope", "intercept", "amplitude", "exponent", "offset"}
    ),
}

_STYLE_PROPERTIES = frozenset(
    {
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "opacity",
        "color",
        "font-family",
        "font-size",
        "font-weight",
        "font-style",
        "letter-spacing",
        "text-anchor",
        "dominant-baseline",
        "alignment-baseline",
        "display",
        "visibility",
        "clip-path",
        "clip-rule",
        "mask",
        "filter",
        "marker-start",
        "marker-mid",
        "marker-end",
    }
)

_LOCAL_FRAGMENT = re.compile(r"^#[A-Za-z_][A-Za-z0-9_.:-]*$")
_LOCAL_URL = re.compile(r"^url\s*\(\s*#[A-Za-z_][A-Za-z0-9_.:-]*\s*\)$", re.IGNORECASE)
_DATA_URI = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _reject(category: str) -> None:
    raise UnsafeSvgContent(detail=category)


def _check_style(value: str) -> None:
    if _CONTROL.search(value) or "/*" in value or "*/" in value:
        _reject("style_content")
    if "@" in value or "expression" in value.lower():
        _reject("style_content")
    declarations: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    paren_depth = 0
    for char in value:
        if escaped:
            _reject("style_escape")
        if char == "\\":
            escaped = True
            current.append(char)
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char == "(":
            paren_depth += 1
            current.append(char)
        elif char == ")":
            paren_depth -= 1
            if paren_depth < 0:
                _reject("style_syntax")
            current.append(char)
        elif char == ";" and paren_depth == 0:
            declarations.append("".join(current))
            current = []
        elif char in "{}":
            _reject("style_syntax")
        else:
            current.append(char)
    if escaped or quote or paren_depth:
        _reject("style_syntax")
    declarations.append("".join(current))

    for declaration in declarations:
        declaration = declaration.strip()
        if not declaration:
            continue
        if ":" not in declaration:
            _reject("style_syntax")
        name, css_value = declaration.split(":", 1)
        if name.strip().lower() not in _STYLE_PROPERTIES or not css_value.strip():
            _reject("style_property")
        for url_match in re.finditer(r"url\s*\([^)]*\)", css_value, re.IGNORECASE):
            if not _LOCAL_URL.fullmatch(url_match.group(0).strip()):
                _reject("style_content")
        if re.search(r"url\s*\(", css_value, re.IGNORECASE) and not re.search(
            r"url\s*\([^)]*\)", css_value, re.IGNORECASE
        ):
            _reject("style_content")


def _check_data_uri(value: str, limits: SvgLimits) -> None:
    match = _DATA_URI.fullmatch(value)
    if not match:
        _reject("external_reference")
    try:
        decoded = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        _reject("data_uri_encoding")
    if len(decoded) > limits.max_data_uri_bytes:
        _reject("data_uri_size")


def _check_url_value(value: str, limits: SvgLimits, *, href: bool = False) -> None:
    if _CONTROL.search(value):
        _reject("control_character")
    stripped = value.strip()
    if href:
        if _LOCAL_FRAGMENT.fullmatch(stripped):
            return
        if stripped.lower().startswith("data:"):
            _check_data_uri(stripped, limits)
            return
        _reject("external_reference")
    if "url(" in stripped.lower() and not _LOCAL_URL.fullmatch(stripped):
        _reject("external_reference")


def _attribute_name(key: str) -> tuple[str | None, str]:
    if key.startswith("{"):
        qname = etree.QName(key)
        return qname.namespace, qname.localname
    return None, key


def _walk_and_validate(root: etree._Element, limits: SvgLimits) -> None:
    root_qname = etree.QName(root)
    if root_qname.localname != "svg" or root_qname.namespace != SVG_NS:
        _reject("root_element")
    count = 0
    for node in root.iter():
        count += 1
        if count > limits.max_elements:
            _reject("element_count")
        depth = 0
        parent = node.getparent()
        while parent is not None:
            depth += 1
            parent = parent.getparent()
        if depth > limits.max_depth:
            _reject("element_depth")
        qname = etree.QName(node)
        if qname.localname not in _ALLOWED_ELEMENTS or qname.namespace != SVG_NS:
            _reject("element_allowlist")
        if len(node.attrib) > limits.max_attributes:
            _reject("attribute_count")
        for key, value in node.attrib.items():
            attr_namespace, attr_name = _attribute_name(key)
            if len(value) > limits.max_attribute_length:
                _reject("attribute_length")
            if _CONTROL.search(value):
                _reject("control_character")
            if attr_name.lower().startswith("on"):
                _reject("event_handler")
            if attr_namespace not in {None, XLINK_NS, XML_NS}:
                _reject("attribute_namespace")
            if attr_namespace == XLINK_NS and attr_name != "href":
                _reject("attribute_allowlist")
            if attr_namespace == XML_NS and attr_name != "space":
                _reject("attribute_allowlist")
            if (
                attr_name not in _GLOBAL_ATTRIBUTES
                and attr_name not in _ELEMENT_ATTRIBUTES.get(qname.localname, frozenset())
                and attr_name != "href"
                and not (attr_namespace == XML_NS and attr_name == "space")
            ):
                _reject("attribute_allowlist")
            if attr_name == "style":
                _check_style(value)
            elif attr_name == "href":
                _check_url_value(value, limits, href=True)
            else:
                _check_url_value(value, limits)


def _parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        remove_comments=True,
        remove_pis=True,
    )


def sanitize_svg(raw: bytes | bytearray | str, *, limits: SvgLimits | None = None) -> SanitizedSvg:
    """Return canonical safe SVG bytes or raise ``UNSAFE_SVG_CONTENT``."""
    limits = limits or SvgLimits()
    data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
    if not data or len(data) > limits.max_bytes:
        _reject("document_size")
    if re.search(br"<!DOCTYPE", data, re.IGNORECASE):
        _reject("doctype")
    try:
        root = etree.fromstring(data, parser=_parser())
    except (etree.XMLSyntaxError, ValueError):
        _reject("xml_syntax")
    _walk_and_validate(root, limits)
    serialized = etree.tostring(root, encoding="utf-8", xml_declaration=True, method="xml")
    if len(serialized) > limits.max_bytes:
        _reject("serialized_size")
    try:
        reparsed = etree.fromstring(serialized, parser=_parser())
        _walk_and_validate(reparsed, limits)
    except (etree.XMLSyntaxError, ValueError):
        _reject("serialization_roundtrip")
    return SanitizedSvg(serialized)


def sanitize_svg_file(path: str | Path, *, limits: SvgLimits | None = None) -> SanitizedSvg:
    try:
        return sanitize_svg(Path(path).read_bytes(), limits=limits)
    except OSError:
        _reject("read_failed")
