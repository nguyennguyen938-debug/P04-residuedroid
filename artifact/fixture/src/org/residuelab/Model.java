package org.residuelab;

import android.content.Context;

/** Fixture tenants (one stated contract each) and enforcement variants (one per installed package). */
public final class Model {
    // ---- job kinds ----
    public static final int K_UPLOAD = 1, K_AGG = 2, K_SUMMARY = 3, K_BACKUP = 4, K_PERSONAL = 5;
    public static int jobId(int tenant, int kind) { return tenant * 10 + kind; }

    /** A tenant is an independent workload in the app with its own stated contract. */
    public static final class Tenant {
        public final int id; public final String name; public final String scope;
        public final String purpose;          // purpose of the main upload
        public final boolean revokesPending;  // withdrawal also invalidates data collected earlier
        public final String revoked;          // purposes revoked by the withdrawal: "*" = all, "" = none, else one purpose
        public final boolean hasSummary;      // aggregator -> derived summary -> summary upload
        public final String summaryDeclared;  // scope the developer declared for the summary job
        public final boolean deletes;         // withdrawal is a deletion request (delete local rows)
        public final boolean unmediated;      // upload bypasses the egress wrapper (raw socket)
        public final boolean opaque;          // upload body is encrypted (sink cannot attribute)
        public final boolean location;        // collection gated by the OS location permission
        public final boolean dualPurpose;     // records uploaded for backup AND personalization
        Tenant(int id, String name, String scope, String purpose, boolean rp, String revoked, boolean sum,
               String sumDecl, boolean del, boolean unmed, boolean opq, boolean loc, boolean dual) {
            this.id = id; this.name = name; this.scope = scope; this.purpose = purpose; this.revokesPending = rp;
            this.revoked = revoked; this.hasSummary = sum; this.summaryDeclared = sumDecl; this.deletes = del;
            this.unmediated = unmed; this.opaque = opq; this.location = loc; this.dualPurpose = dual;
        }
        public boolean revokes(String p) { return revoked.equals("*") || revoked.equals(p); }
    }

    public static final Tenant[] TENANTS = new Tenant[]{
        null,
        // id name               scope        purpose      revPend revoked  summary declSum       del    unmed  opaque loc   dual
        new Tenant(1, "optout-misdecl", "analytics", "analytics", true,  "*", true,  "diagnostics", false, false, false, false, false),
        new Tenant(2, "delete",         "analytics", "analytics", true,  "*", true,  "analytics",   true,  false, false, false, false),
        new Tenant(3, "optout-flush",   "analytics", "analytics", false, "*", true,  "analytics",   false, false, false, false, false),
        new Tenant(4, "restrict",       "profile",   "backup",    true,  "personalization", false, "", false, false, false, false, true),
        new Tenant(5, "reconsent",      "analytics", "analytics", true,  "*", true,  "analytics",   false, false, false, false, false),
        new Tenant(6, "control",        "analytics", "analytics", true,  "*", true,  "analytics",   false, false, false, false, false),
        new Tenant(7, "os-location",    "location",  "history",   true,  "",  false, "",            false, false, false, true,  false),
        new Tenant(8, "optout-decl",    "analytics", "analytics", true,  "*", true,  "analytics",   false, false, false, false, false),
        new Tenant(9, "unmediated",     "analytics", "analytics", true,  "*", false, "",            false, true,  false, false, false),
        new Tenant(10,"opaque",         "analytics", "analytics", true,  "*", false, "",            false, false, true,  false, false),
    };

    /** Enforcement variant, derived from the package-name suffix. */
    public static final class Variant {
        public final String name;
        public boolean cancel, enqueueCheck, jobStartCheck, egressCheck, lineage, durable, contractAware, serialize;
        public boolean matched, chunk, retryCheck;
        public long raceDelayMs = 0; // only for the serialization micro-experiment
        Variant(String n) { name = n; }
    }

    private static Variant cached;
    public static synchronized Variant variant(Context c) {
        if (cached != null) return cached;
        String p = c.getPackageName();
        String n = p.substring(p.lastIndexOf('.') + 1);
        if (n.startsWith("al") || n.startsWith("wm")) n = n.substring(2);   // AlarmManager / WorkManager substrate builds
        Variant v = new Variant(n);
        switch (n) {
            case "tls": case "menqueue": case "mstart": case "mlayer": case "mfence": case "mboth":
                v.matched = true; v.chunk = true; v.lineage = true; v.durable = true; v.contractAware = true;
                v.enqueueCheck = n.equals("menqueue") || n.equals("mlayer") || n.equals("mboth");
                v.jobStartCheck = n.equals("mstart") || n.equals("mlayer") || n.equals("mboth");
                v.retryCheck = n.equals("mlayer") || n.equals("mboth");
                v.cancel = v.retryCheck;
                v.egressCheck = n.equals("mfence") || n.equals("mboth"); v.serialize = v.egressCheck;
                break;
            case "none": break;
            case "cancel": v.cancel = true; break;
            case "enqueue": v.enqueueCheck = true; break;
            case "jobstart": v.jobStartCheck = true; break;
            case "conv": v.cancel = true; v.enqueueCheck = true; v.jobStartCheck = true; break;
            case "egress": v.egressCheck = true; v.serialize = true; break;
            case "rd": v.egressCheck = true; v.lineage = true; v.durable = true; v.contractAware = true; v.serialize = true; break;
            case "volatile": v.egressCheck = true; v.lineage = true; v.durable = false; v.contractAware = true; v.serialize = true; break;
            case "taint": v.egressCheck = true; v.lineage = true; v.durable = true; v.contractAware = false; v.serialize = true; break;
            case "noser": v.egressCheck = true; v.lineage = true; v.durable = true; v.contractAware = true; v.serialize = false; break;
            default: break;
        }
        cached = v;
        return v;
    }
}
