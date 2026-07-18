import assert from 'node:assert/strict';
import test from 'node:test';

import { emitAppEvent, onAppEvent } from '../src/app-events.js';

test('app events deliver payloads to active subscribers', () => {
  const eventName = 'test:payload';
  const received = [];
  const unsubscribe = onAppEvent(eventName, payload => received.push(payload));

  emitAppEvent(eventName, { value: 42 });
  unsubscribe();

  assert.deepEqual(received, [{ value: 42 }]);
});

test('unsubscribed app event listeners are not called', () => {
  const eventName = 'test:unsubscribe';
  let callCount = 0;
  const unsubscribe = onAppEvent(eventName, () => {
    callCount += 1;
  });

  unsubscribe();
  emitAppEvent(eventName);

  assert.equal(callCount, 0);
});

test('subscribing the same listener twice does not duplicate calls', () => {
  const eventName = 'test:deduplicate';
  let callCount = 0;
  const listener = () => {
    callCount += 1;
  };
  const unsubscribeFirst = onAppEvent(eventName, listener);
  const unsubscribeSecond = onAppEvent(eventName, listener);

  emitAppEvent(eventName);
  unsubscribeFirst();
  unsubscribeSecond();

  assert.equal(callCount, 1);
});
