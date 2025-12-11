Compatibility middleware example (pseudo-code)

Purpose: Convert /api/v2/orders responses into v1-compatible payload for legacy clients.

Pseudo-code (Python-like):

```
def v2_to_v1(order):
    # Map field renames
    order_v1 = {}
    order_v1['orderId'] = order.get('orderId')
    order_v1['status'] = order.get('state') or 'UNKNOWN'
    order_v1['totalPrice'] = order.get('amount')

    # Ensure items exists
    if 'lineItems' in order and order['lineItems'] is not None:
        order_v1['items'] = [
            {'productName': li.get('name'), 'qty': li.get('quantity')} for li in order['lineItems']
        ]
    else:
        order_v1['items'] = []  # safe default, no null pointers

    # Map new states to known enums; default to UNKNOWN
    known_states_map = {
        'PAID': 'PAID',
        'CANCELLED': 'CANCELLED',
        'SHIPPED': 'SHIPPED'
    }
    if order_v1['status'] not in known_states_map:
        order_v1['status'] = 'UNKNOWN'  # or a safe fallback mapping

    return order_v1
```

Operational notes:
- Logging at map time is crucial: record any unknown state encountered for later analysis.
- This can be implemented at API gateway, a service mesh, or a dedicated compatibility microservice.
- For new clients, migrate them to v2 or update code to read v2 schema; phased rollout is recommended.
