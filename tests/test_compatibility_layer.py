import json

# Sample implementation of the compatibility mapping function used by the service gateway

def _v2_to_v1(order):
    order_v1 = {}
    order_v1['orderId'] = order.get('orderId')
    order_v1['status'] = order.get('state') or 'UNKNOWN'
    order_v1['totalPrice'] = order.get('amount')

    if 'lineItems' in order and order['lineItems'] is not None:
        order_v1['items'] = [{'productName': li.get('name'), 'qty': li.get('quantity')} for li in order['lineItems']]
    else:
        order_v1['items'] = []

    known_states = {'PAID', 'CANCELLED', 'SHIPPED'}
    if order_v1['status'] not in known_states:
        order_v1['status'] = 'UNKNOWN'
    return order_v1


def test_mapping_lineItems_present():
    v2 = {
        "orderId": "ORD-789",
        "state": "SHIPPED",
        "amount": 59.5,
        "lineItems": [{"name": "Pen", "quantity": 3}, {"name": "Notebook", "quantity": 2}]
    }
    v1 = _v2_to_v1(v2)
    assert v1['status'] == 'SHIPPED'
    assert v1['totalPrice'] == 59.5
    assert isinstance(v1['items'], list) and v1['items'][0]['productName'] == 'Pen'


def test_mapping_lineItems_absent():
    v2 = {"orderId": "ORD-123", "state": "PAID", "amount": 199.99}
    v1 = _v2_to_v1(v2)
    assert v1['items'] == []


def test_mapping_unknown_state():
    v2 = {"orderId": "ORD-555", "state": "FULFILLED", "amount": 120.0}
    v1 = _v2_to_v1(v2)
    assert v1['status'] == 'UNKNOWN'
