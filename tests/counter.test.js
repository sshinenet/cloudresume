import assert from "node:assert/strict";
import { test } from "node:test";

import { LAST_VISIT_KEY, resolveVisitorCount, todayUTC } from "../counter.js";

const API = "https://example.invalid/count";

function fakeStorage(initial = {}, { throwOnGet = false, throwOnSet = false } = {}) {
    const data = { ...initial };
    return {
        data,
        getItem(key) {
            if (throwOnGet) throw new Error("storage unavailable");
            return key in data ? data[key] : null;
        },
        setItem(key, value) {
            if (throwOnSet) throw new Error("storage unavailable");
            data[key] = value;
        },
    };
}

function fakeFetch(response) {
    const calls = [];
    const fn = async (url, options) => {
        calls.push({ url, method: options?.method });
        return response;
    };
    fn.calls = calls;
    return fn;
}

const okWith = (body) => ({ ok: true, json: async () => body });
const notOk = () => ({ ok: false, json: async () => ({}) });
const unparseable = () => ({
    ok: true,
    json: async () => {
        throw new SyntaxError("Unexpected token");
    },
});

const JAN_2 = new Date("2026-01-02T10:00:00Z");

test("a first-ever visit increments via POST and returns the new count", async () => {
    const fetchFn = fakeFetch(okWith({ count: 1 }));

    const count = await resolveVisitorCount({
        fetchFn,
        storage: fakeStorage(),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, 1);
    assert.deepEqual(fetchFn.calls, [{ url: API, method: "POST" }]);
});

test("a first-ever visit records today so it is not counted twice", async () => {
    const storage = fakeStorage();

    await resolveVisitorCount({
        fetchFn: fakeFetch(okWith({ count: 1 })),
        storage,
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(storage.data[LAST_VISIT_KEY], "2026-01-02");
});

test("a repeat visit on the same day reads via GET without incrementing", async () => {
    const fetchFn = fakeFetch(okWith({ count: 7 }));

    const count = await resolveVisitorCount({
        fetchFn,
        storage: fakeStorage({ [LAST_VISIT_KEY]: "2026-01-02" }),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, 7);
    assert.deepEqual(fetchFn.calls, [{ url: API, method: "GET" }]);
});

test("a visit on a later day increments again", async () => {
    const fetchFn = fakeFetch(okWith({ count: 8 }));

    await resolveVisitorCount({
        fetchFn,
        storage: fakeStorage({ [LAST_VISIT_KEY]: "2026-01-01" }),
        apiUrl: API,
        now: JAN_2,
    });

    assert.deepEqual(fetchFn.calls, [{ url: API, method: "POST" }]);
});

test("storage that refuses reads is treated as a fresh visit", async () => {
    const fetchFn = fakeFetch(okWith({ count: 1 }));

    const count = await resolveVisitorCount({
        fetchFn,
        storage: fakeStorage({}, { throwOnGet: true }),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, 1);
    assert.deepEqual(fetchFn.calls, [{ url: API, method: "POST" }]);
});

test("storage that refuses writes still returns the count", async () => {
    const count = await resolveVisitorCount({
        fetchFn: fakeFetch(okWith({ count: 4 })),
        storage: fakeStorage({}, { throwOnSet: true }),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, 4);
});

test("an error response yields null rather than throwing", async () => {
    const count = await resolveVisitorCount({
        fetchFn: fakeFetch(notOk()),
        storage: fakeStorage(),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, null);
});

test("an unparseable body yields null rather than throwing", async () => {
    const count = await resolveVisitorCount({
        fetchFn: fakeFetch(unparseable()),
        storage: fakeStorage(),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, null);
});

test("a non-numeric count yields null", async () => {
    const count = await resolveVisitorCount({
        fetchFn: fakeFetch(okWith({ count: "lots" })),
        storage: fakeStorage(),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, null);
});

test("a network failure yields null rather than throwing", async () => {
    const exploding = async () => {
        throw new TypeError("Failed to fetch");
    };

    const count = await resolveVisitorCount({
        fetchFn: exploding,
        storage: fakeStorage(),
        apiUrl: API,
        now: JAN_2,
    });

    assert.equal(count, null);
});

test("todayUTC does not drift with local timezone", () => {
    assert.equal(todayUTC(new Date("2026-03-09T23:30:00Z")), "2026-03-09");
    assert.equal(todayUTC(new Date("2026-03-10T00:30:00Z")), "2026-03-10");
});
