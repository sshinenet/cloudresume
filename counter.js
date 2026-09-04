// Visitor-counter logic, kept free of browser globals so it can be tested
// directly. `fetchFn` and `storage` are injected by main.js.

export const LAST_VISIT_KEY = "stevenshine-last-visit";

// UTC so the "one count per day" boundary does not shift with the visitor's
// timezone or with travel.
export function todayUTC(now = new Date()) {
    return now.toISOString().slice(0, 10);
}

function readLastVisit(storage) {
    try {
        return storage.getItem(LAST_VISIT_KEY);
    } catch (e) {
        // Private mode or blocked storage: treat as a visitor we have not seen.
        return null;
    }
}

function rememberVisit(storage, day) {
    try {
        storage.setItem(LAST_VISIT_KEY, day);
    } catch (e) {
        // Not being able to remember is fine; the count still displays.
    }
}

/**
 * Returns the visitor count, or null if it could not be determined.
 * Increments at most once per browser per UTC day.
 */
export async function resolveVisitorCount({
    fetchFn,
    storage,
    apiUrl,
    now = new Date(),
}) {
    const day = todayUTC(now);
    const countedAlready = readLastVisit(storage) === day;

    try {
        const response = await fetchFn(apiUrl, {
            method: countedAlready ? "GET" : "POST",
        });
        if (!response.ok) return null;

        const { count } = await response.json();
        if (typeof count !== "number") return null;

        if (!countedAlready) rememberVisit(storage, day);
        return count;
    } catch (e) {
        // The counter is decorative. It must never break the page.
        return null;
    }
}
