# Joi VRM Audit

Captured from `frontend/public/avatar/models/vroid-joi/joi-vroid-v1.vrm`.

## Asset

- generator: `VRoid Studio-2.12.0`
- glTF version: `2.0`

## License Metadata

- authors: `avsmills`
- commercial usage: `personalNonProfit`
- credit notation: `unnecessary`

## Expression Presets

- `happy`
- `angry`
- `sad`
- `relaxed`
- `surprised`
- `aa`
- `ih`
- `ou`
- `ee`
- `oh`
- `blink`
- `blinkLeft`
- `blinkRight`
- `neutral`

## Custom Expressions

None.

## Human Bones

- `hips`
- `spine`
- `chest`
- `upperChest`
- `neck`
- `head`
- `leftEye`
- `rightEye`
- `leftUpperLeg`
- `leftLowerLeg`
- `leftFoot`
- `leftToes`
- `rightUpperLeg`
- `rightLowerLeg`
- `rightFoot`
- `rightToes`
- `leftShoulder`
- `leftUpperArm`
- `leftLowerArm`
- `leftHand`
- `rightShoulder`
- `rightUpperArm`
- `rightLowerArm`
- `rightHand`
- `leftThumbMetacarpal`
- `leftThumbProximal`
- `leftThumbDistal`
- `leftIndexProximal`
- `leftIndexIntermediate`
- `leftIndexDistal`
- `leftMiddleProximal`
- `leftMiddleIntermediate`
- `leftMiddleDistal`
- `leftRingProximal`
- `leftRingIntermediate`
- `leftRingDistal`
- `leftLittleProximal`
- `leftLittleIntermediate`
- `leftLittleDistal`
- `rightThumbMetacarpal`
- `rightThumbProximal`
- `rightThumbDistal`
- `rightIndexProximal`
- `rightIndexIntermediate`
- `rightIndexDistal`
- `rightMiddleProximal`
- `rightMiddleIntermediate`
- `rightMiddleDistal`
- `rightRingProximal`
- `rightRingIntermediate`
- `rightRingDistal`
- `rightLittleProximal`
- `rightLittleIntermediate`
- `rightLittleDistal`

## Spring Bone Metadata

- springs: 27
- collider groups: 12
- colliders: 28
- named spring groups include `Bust`, `Skirt`, and `Hair`

## Implementation Notes

- Runtime expression mapping should target presets only. This asset does not provide custom `smirk`, `concern`, or `stress` expressions.
- Gaze can use `leftEye` and `rightEye` bones in addition to head and neck settling.
- Lip-sync can use VRM viseme presets: `aa`, `ih`, `ou`, `ee`, and `oh`.
- License metadata should be reviewed before public/commercial distribution because commercial usage is marked `personalNonProfit`.
