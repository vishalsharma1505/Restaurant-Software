const socket = io();

document.getElementById('placeOrder').addEventListener('click', () => {
    const tableId = document.getElementById('table').value;
    const products = [];
    document.querySelectorAll('.qty').forEach(input => {
        const qty = parseInt(input.value);
        if (qty > 0) {
            products.push({id: input.dataset.id, qty: qty});
        }
    });

    if (products.length === 0) {
        alert('Select at least one product');
        return;
    }

    socket.emit('new_order', {table_id: tableId, products: products});
});

// Listen for updates
socket.on('update_orders', orders => {
    const ordersList = document.getElementById('ordersList');
    ordersList.innerHTML = '';
    orders.forEach(order => {
        const li = document.createElement('li');
        li.textContent = `Table: ${order.table} | Status: ${order.status}`;
        ordersList.appendChild(li);
    });
});
