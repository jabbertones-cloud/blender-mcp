import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import sharp from 'sharp';
import { Document, NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { prune } from '@gltf-transform/functions';
import validator from 'gltf-validator';

const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url)));
const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url)));

test('secure and reproducible npm dependency graph', () => {
  assert.equal(manifest.engines.node, '>=20.9.0');
  assert.equal(manifest.dependencies.sharp, undefined);
  assert.equal(lock.lockfileVersion, 3);
  assert.deepEqual(lock.packages[''].dependencies, manifest.dependencies);
  assert.equal(lock.packages['node_modules/@gltf-transform/functions'].version, '4.5.1');
  assert.equal(lock.packages['node_modules/ndarray-pixels'].version, '5.2.0');
  assert.equal(lock.packages['node_modules/sharp'].version, '0.35.5');
  assert.equal(lock.packages['node_modules/ndarray-pixels/node_modules/sharp'], undefined);
});

test('native patched sharp still produces a valid PNG', async () => {
  const png = await sharp({create:{width:4,height:4,channels:4,background:'#44aaff'}}).png().toBuffer();
  assert.deepEqual(png.subarray(0,8),Buffer.from([137,80,78,71,13,10,26,10]));
  assert.equal(sharp.versions.sharp, '0.35.5');
});

test('upgraded glTF Transform roundtrips a real triangle through glTF Validator', async () => {
  const document = new Document();
  const buffer = document.createBuffer();
  const positions = document.createAccessor('TrianglePositions').setType('VEC3')
    .setArray(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0])).setBuffer(buffer);
  const primitive = document.createPrimitive().setAttribute('POSITION', positions);
  const mesh = document.createMesh('SecuritySmokeTriangle').addPrimitive(primitive);
  document.createScene('DependencySecuritySmoke').addChild(document.createNode('Triangle').setMesh(mesh));
  await document.transform(prune());
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const glb = await io.writeBinary(document);
  const roundtrip = await io.readBinary(glb);
  assert.equal(roundtrip.getRoot().listMeshes().length, 1);
  const report = await validator.validateBytes(new Uint8Array(glb));
  assert.equal(report.issues.numErrors, 0);
  assert.equal(report.issues.numWarnings, 0);
});
