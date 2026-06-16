import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSeedValue;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSeedValueCertificate;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSeedValueMDP;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSeedValueTimeStamp;

/**
 * Live oracle probe: malformed /SV seed-value sub-dictionary accessor surface.
 *
 * Rather than round-trip through a PDF file, this probe constructs the seed
 * value (/Type /SV) COSDictionary for a named fuzz CASE entirely in-memory,
 * then projects EVERY public PDSeedValue / PDSeedValueCertificate /
 * PDSeedValueMDP / PDSeedValueTimeStamp accessor, catching any exception per
 * accessor and reporting it as {@code err.<SimpleExceptionName>}. The Python
 * side (test_seed_value_fuzz_wave1538.py) builds the identical COS dict with
 * pypdfbox and projects the identical accessors, so each line is a true
 * differential.
 *
 * CASE values (argv[0]):
 *   empty               — bare {/Type /SV}, no /Ff, no entries
 *   ff_missing          — same as empty (flag-default probe)
 *   ff_all_bits         — /Ff = 0x7F (all seven required bits set)
 *   ff_filter_only      — /Ff = 1
 *   subfilter_names     — /SubFilter as array of names (well-formed)
 *   subfilter_strings   — /SubFilter as array of text strings (wrong type)
 *   subfilter_notarray  — /SubFilter as a bare name (wrong type)
 *   reasons_strings     — /Reasons as array of text strings (spec-correct)
 *   reasons_names       — /Reasons as array of names
 *   digest_names        — /DigestMethod as array of names (well-formed)
 *   v_float             — /V = 1.5
 *   v_int               — /V = 2
 *   v_missing           — no /V
 *   v_wrongtype         — /V = (Hi) string
 *   mdp_p0..mdp_p3      — /MDP {/P n}
 *   mdp_nop             — /MDP {} (no /P)
 *   mdp_missing         — no /MDP
 *   ts_url_req          — /TimeStamp {/URL .. /Ff 1}
 *   ts_url_noff         — /TimeStamp {/URL ..}
 *   ts_missing          — no /TimeStamp
 *   cert_subj_url       — /Cert {/Ff .. /URL .. /URLType ..}
 *   cert_missing        — no /Cert
 *   filter_name         — /Filter as a name
 *   filter_string       — /Filter as a text string
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SeedValueFuzzProbe <case>
 */
public final class SeedValueFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String kase = args[0];

        COSDictionary sv = new COSDictionary();
        sv.setItem(COSName.TYPE, COSName.getPDFName("SV"));
        build(sv, kase);

        PDSeedValue seed = new PDSeedValue(sv);
        TreeMap<String, Object> root = new TreeMap<>();

        // ---- flag predicates ----
        put(root, "filterReq", () -> seed.isFilterRequired());
        put(root, "subFilterReq", () -> seed.isSubFilterRequired());
        put(root, "vReq", () -> seed.isVRequired());
        put(root, "reasonReq", () -> seed.isReasonRequired());
        put(root, "legalReq", () -> seed.isLegalAttestationRequired());
        put(root, "addRevReq", () -> seed.isAddRevInfoRequired());
        put(root, "digestReq", () -> seed.isDigestMethodRequired());

        // ---- scalar / array accessors ----
        put(root, "filter", () -> seed.getFilter());
        put(root, "subFilter", () -> seed.getSubFilter());
        put(root, "reasons", () -> seed.getReasons());
        put(root, "digestMethod", () -> seed.getDigestMethod());
        put(root, "legalAttestation", () -> seed.getLegalAttestation());
        put(root, "v", () -> (double) seed.getV());

        // ---- sub-dict presence + projected scalars ----
        put(root, "mdpPresent", () -> seed.getMDP() != null);
        put(root, "mdpP", () -> {
            PDSeedValueMDP mdp = seed.getMDP();
            return mdp == null ? -1 : mdp.getP();
        });
        put(root, "tsPresent", () -> seed.getTimeStamp() != null);
        put(root, "tsUrl", () -> {
            PDSeedValueTimeStamp ts = seed.getTimeStamp();
            return ts == null ? null : ts.getURL();
        });
        put(root, "tsReq", () -> {
            PDSeedValueTimeStamp ts = seed.getTimeStamp();
            return ts == null ? false : ts.isTimestampRequired();
        });
        put(root, "certPresent", () -> seed.getSeedValueCertificate() != null);
        put(root, "certUrl", () -> {
            PDSeedValueCertificate c = seed.getSeedValueCertificate();
            return c == null ? null : c.getURL();
        });
        put(root, "certUrlType", () -> {
            PDSeedValueCertificate c = seed.getSeedValueCertificate();
            return c == null ? null : c.getURLType();
        });
        put(root, "certSubjReq", () -> {
            PDSeedValueCertificate c = seed.getSeedValueCertificate();
            return c == null ? false : c.isSubjectRequired();
        });
        put(root, "certUrlReq", () -> {
            PDSeedValueCertificate c = seed.getSeedValueCertificate();
            return c == null ? false : c.isURLRequired();
        });

        out.print(jsonify(root));
    }

    private static void build(COSDictionary sv, String kase) {
        switch (kase) {
            case "empty":
            case "ff_missing":
                break;
            case "ff_all_bits":
                sv.setInt(COSName.FF, 0x7F);
                break;
            case "ff_filter_only":
                sv.setInt(COSName.FF, 1);
                break;
            case "subfilter_names": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("adbe.pkcs7.detached"));
                a.add(COSName.getPDFName("ETSI.CAdES.detached"));
                sv.setItem(COSName.getPDFName("SubFilter"), a);
                break;
            }
            case "subfilter_strings": {
                COSArray a = new COSArray();
                a.add(new COSString("adbe.pkcs7.detached"));
                sv.setItem(COSName.getPDFName("SubFilter"), a);
                break;
            }
            case "subfilter_notarray":
                sv.setItem(COSName.getPDFName("SubFilter"),
                        COSName.getPDFName("adbe.pkcs7.detached"));
                break;
            case "reasons_strings": {
                COSArray a = new COSArray();
                a.add(new COSString("I approve"));
                a.add(new COSString("I reviewed"));
                sv.setItem(COSName.getPDFName("Reasons"), a);
                break;
            }
            case "reasons_names": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("approve"));
                sv.setItem(COSName.getPDFName("Reasons"), a);
                break;
            }
            case "digest_names": {
                COSArray a = new COSArray();
                a.add(COSName.getPDFName("SHA256"));
                a.add(COSName.getPDFName("SHA512"));
                sv.setItem(COSName.getPDFName("DigestMethod"), a);
                break;
            }
            case "v_float":
                sv.setItem(COSName.V, new COSFloat(1.5f));
                break;
            case "v_int":
                sv.setItem(COSName.V, COSInteger.get(2));
                break;
            case "v_missing":
                break;
            case "v_wrongtype":
                sv.setItem(COSName.V, new COSString("Hi"));
                break;
            case "mdp_p0":
            case "mdp_p1":
            case "mdp_p2":
            case "mdp_p3": {
                COSDictionary mdp = new COSDictionary();
                mdp.setInt(COSName.P, kase.charAt(5) - '0');
                sv.setItem(COSName.getPDFName("MDP"), mdp);
                break;
            }
            case "mdp_nop":
                sv.setItem(COSName.getPDFName("MDP"), new COSDictionary());
                break;
            case "mdp_missing":
                break;
            case "ts_url_req": {
                COSDictionary ts = new COSDictionary();
                ts.setString(COSName.getPDFName("URL"), "https://tsa.example/ts");
                ts.setInt(COSName.FF, 1);
                sv.setItem(COSName.getPDFName("TimeStamp"), ts);
                break;
            }
            case "ts_url_noff": {
                COSDictionary ts = new COSDictionary();
                ts.setString(COSName.getPDFName("URL"), "https://tsa.example/ts");
                sv.setItem(COSName.getPDFName("TimeStamp"), ts);
                break;
            }
            case "ts_missing":
                break;
            case "cert_subj_url": {
                COSDictionary cert = new COSDictionary();
                cert.setInt(COSName.FF, 1 | (1 << 6)); // subject + url required
                cert.setString(COSName.getPDFName("URL"), "https://ca.example/enroll");
                cert.setName(COSName.getPDFName("URLType"), "ASSP");
                sv.setItem(COSName.getPDFName("Cert"), cert);
                break;
            }
            case "cert_missing":
                break;
            case "filter_name":
                sv.setItem(COSName.FILTER, COSName.getPDFName("Adobe.PPKLite"));
                break;
            case "filter_string":
                sv.setItem(COSName.FILTER, new COSString("Adobe.PPKLite"));
                break;
            default:
                throw new IllegalArgumentException("unknown case: " + kase);
        }
    }

    // -- run a projection; on any exception emit err.<SimpleName> instead --

    private interface Proj {
        Object get();
    }

    private static void put(TreeMap<String, Object> root, String key, Proj p) {
        try {
            root.put(key, p.get());
        } catch (Throwable t) {
            root.put(key, "err." + t.getClass().getSimpleName());
        }
    }

    // --- minimal JSON emitter (TreeMap / List / String / Number / Boolean) ---

    private static String jsonify(Object value) {
        StringBuilder sb = new StringBuilder();
        emit(sb, value);
        return sb.toString();
    }

    private static void emit(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof Map<?, ?> map) {
            sb.append("{");
            boolean first = true;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!first) {
                    sb.append(",");
                }
                first = false;
                emitString(sb, String.valueOf(entry.getKey()));
                sb.append(":");
                emit(sb, entry.getValue());
            }
            sb.append("}");
        } else if (value instanceof List<?> list) {
            sb.append("[");
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    sb.append(",");
                }
                emit(sb, list.get(i));
            }
            sb.append("]");
        } else if (value instanceof Number || value instanceof Boolean) {
            sb.append(value.toString());
        } else {
            emitString(sb, value.toString());
        }
    }

    private static void emitString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }
}
