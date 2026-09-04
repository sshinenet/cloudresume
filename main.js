/*
come on. what are you doing?
linkedin.com/in/stevenshine
*/

import { resolveVisitorCount } from "./counter.js";

const COUNTER_API = "https://pnl79soijj.execute-api.us-east-1.amazonaws.com/count";

// Some browsers throw on the property access itself when site data is blocked,
// so this cannot wait until the first getItem call.
function storage() {
    try {
        return window.localStorage;
    } catch (e) {
        return { getItem: () => null, setItem: () => {} };
    }
}

async function showVisitorCount() {
    const count = await resolveVisitorCount({
        fetchFn: (url, options) => fetch(url, options),
        storage: storage(),
        apiUrl: COUNTER_API,
    });

    if (count === null) return;

    document.getElementById("visitor-count").textContent = count.toLocaleString();
    document.getElementById("visitor-line").hidden = false;
}

showVisitorCount();
