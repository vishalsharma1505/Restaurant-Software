let order = {};

function addToOrder(id) {
    order[id] = (order[id] || 0) + 1;
    updateTotal();
}

function removeFromOrder(id) {
    if(order[id]) order[id]--;
    if(order[id] === 0) delete order[id];
    updateTotal();
}

function updateTotal() {
    let total = 0;
    for(let key in order){
        let price = parseFloat(document.getElementById("price_" + key).innerText);
        total += order[key] * price;
    }
    document.getElementById("total").innerText = total.toFixed(2);
}

function submitOrder() {
    alert("Order Submitted: " + JSON.stringify(order));
}
