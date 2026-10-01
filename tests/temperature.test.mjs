import test from 'node:test';
import assert from 'node:assert/strict';
import {toF,toC,preheatC,fahrenheitText} from '../web/temperature.js';

test('Fahrenheit entry round-trips to native machine setpoints',()=>{
  for(const c of [100,160,200,230,310])assert.ok(Math.abs(toC(toF(c))-c)<1e-10);
  assert.equal(toF(230),446);
  assert.equal(preheatC(446),230);
  assert.equal(preheatC(590),310);
});
test('Celsius source prose and ranges display in Fahrenheit',()=>{
  assert.equal(fahrenheitText('Preheat 200°C; drop 205–210 °C.'),'Preheat 392 °F; drop 401–410 °F.');
  assert.equal(fahrenheitText('Water: 100 degrees Celsius; room -10 C.'),'Water: 212 °F; room 14 °F.');
  assert.equal(fahrenheitText('160 to 220 Celsius'),'320–428 °F');
});
test('rates and differences never receive the temperature offset',()=>{
  assert.equal(fahrenheitText('RoR 10 °C/min; decrease by 5°C.'),'RoR 18 °F/min; decrease by 9 °F.');
  assert.equal(fahrenheitText('A 5–10°C reduction. RoR: 8 C.'),'A 9–18 °F reduction. RoR: 14.4 °F.');
});
test('Fahrenheit, machine controls and unlabelled values are preserved',()=>{
  assert.equal(fahrenheitText('P7 F3 D9, 446°F, 250 g, 05:30.'),'P7 F3 D9, 446°F, 250 g, 05:30.');
});
