import type { VRM } from "@pixiv/three-vrm";

type UnknownRecord = Record<string, unknown>;

export type VrmAuditOutput = {
  capturedAt: string;
  meta: unknown;
  license: Record<string, unknown>;
  expressions: {
    all: string[];
    presets: string[];
    custom: string[];
  };
  bones: string[];
  springBones: {
    hasManager: boolean;
    groups: string[];
    joints: string[];
    rawCounts: Record<string, number>;
  };
  capabilities: {
    hasLookAt: boolean;
    hasSpringBones: boolean;
  };
};

declare global {
  interface Window {
    __JOI_VRM_AUDIT__?: VrmAuditOutput;
  }
}

function keysFrom(value: unknown): string[] {
  if (!value) {
    return [];
  }

  if (value instanceof Map) {
    return Array.from(value.keys()).map(String).sort();
  }

  if (Array.isArray(value)) {
    return value
      .map((entry, index) => {
        if (entry && typeof entry === "object" && "name" in entry) {
          return String((entry as { name?: unknown }).name);
        }
        return String(index);
      })
      .sort();
  }

  if (typeof value === "object") {
    return Object.keys(value as UnknownRecord).sort();
  }

  return [];
}

function countFrom(value: unknown): number {
  if (!value) {
    return 0;
  }
  if (value instanceof Map || value instanceof Set) {
    return value.size;
  }
  if (Array.isArray(value)) {
    return value.length;
  }
  if (typeof value === "object") {
    return Object.keys(value as UnknownRecord).length;
  }
  return 0;
}

function pickLicense(meta: unknown): Record<string, unknown> {
  if (!meta || typeof meta !== "object") {
    return {};
  }

  const source = meta as UnknownRecord;
  const fields = [
    "allowedUserName",
    "violentUsageName",
    "sexualUsageName",
    "commercialUsageName",
    "licenseName",
    "licenseUrl",
    "otherLicenseUrl",
    "otherPermissionUrl",
    "copyrightInformation",
    "contactInformation",
    "author",
    "version",
  ];

  return Object.fromEntries(fields.map((field) => [field, source[field]]).filter(([, value]) => value));
}

function springBoneAudit(vrm: VRM) {
  const manager = vrm.springBoneManager as unknown as UnknownRecord | undefined;
  const groupCandidates = [
    keysFrom(manager?.springBoneGroupList),
    keysFrom(manager?.springBoneGroups),
    keysFrom(manager?.springs),
  ];
  const jointCandidates = [
    keysFrom(manager?.joints),
    keysFrom(manager?.springBoneJointList),
    keysFrom(manager?.springBoneJoints),
  ];
  const groups = groupCandidates.find((candidate) => candidate.length > 0) ?? [];
  const joints = jointCandidates.find((candidate) => candidate.length > 0) ?? [];

  return {
    hasManager: Boolean(manager),
    groups,
    joints,
    rawCounts: {
      springBoneGroupList: countFrom(manager?.springBoneGroupList),
      springBoneGroups: countFrom(manager?.springBoneGroups),
      springs: countFrom(manager?.springs),
      joints: countFrom(manager?.joints),
      springBoneJointList: countFrom(manager?.springBoneJointList),
      springBoneJoints: countFrom(manager?.springBoneJoints),
    },
  };
}

export function auditVrm(vrm: VRM): VrmAuditOutput {
  const expressionManager = vrm.expressionManager as unknown as UnknownRecord | undefined;
  const expressionKeys = keysFrom(expressionManager?.expressionMap);
  const presetKeys = keysFrom(expressionManager?.presetExpressionMap);
  const customKeys = keysFrom(expressionManager?.customExpressionMap);
  const boneKeys = keysFrom(vrm.humanoid.humanBones);
  const springBones = springBoneAudit(vrm);

  const audit: VrmAuditOutput = {
    capturedAt: new Date().toISOString(),
    meta: vrm.meta,
    license: pickLicense(vrm.meta),
    expressions: {
      all: expressionKeys,
      presets: presetKeys,
      custom: customKeys,
    },
    bones: boneKeys,
    springBones,
    capabilities: {
      hasLookAt: Boolean(vrm.lookAt),
      hasSpringBones: springBones.hasManager,
    },
  };

  if (typeof window !== "undefined") {
    window.__JOI_VRM_AUDIT__ = audit;
    window.dispatchEvent(new CustomEvent<VrmAuditOutput>("joi-vrm-audit", { detail: audit }));
  }

  console.groupCollapsed("[Joi avatar] VRM audit");
  console.info("Full audit is also available at window.__JOI_VRM_AUDIT__", audit);
  console.table({
    expressions: expressionKeys.length,
    presets: presetKeys.length,
    customExpressions: customKeys.length,
    bones: boneKeys.length,
    springBoneGroups: springBones.groups.length,
    springBoneJoints: springBones.joints.length,
    hasLookAt: audit.capabilities.hasLookAt,
  });
  console.groupEnd();

  return audit;
}
