import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSeedValue;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSeedValueMDP;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDSignatureField;

/**
 * Live oracle probe: signature-field /Lock + /SV seed-value accessor surface
 * NOT covered by SigFieldProbe — the /Lock /Action All/Exclude variants and
 * /P permission level, and the /SV /Filter, /V version, /MDP /P, and
 * /AddRevInfo required-flag.
 *
 * Drives Apache PDFBox 3.0.7's real typed accessors where they exist:
 *   - PDSeedValue.getFilter()           -> sv.filter
 *   - PDSeedValue.getV()                -> sv.v          (float; -1.0 absent)
 *   - PDSeedValue.getMDP().getP()       -> sv.mdpP       (-1 when /MDP absent)
 *   - PDSeedValue.isAddRevInfoRequired()-> sv.addRevInfoReq
 *
 * PDFBox 3.0.7's PDSignatureField has NO getLock() accessor (there is no
 * PDSignatureLock class upstream), so /Lock is read straight off the field's
 * COS dictionary — the spec-defined facts (/Action name, /Fields strings,
 * /P integer) pypdfbox's typed PDSignatureLock wrapper must reproduce.
 *
 * Emits a single canonical JSON object. Absent scalar fields are omitted;
 * the Python side mirrors the same emit rules so the comparison is exact.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SigFieldLockSeedProbe doc.pdf
 */
public final class SigFieldLockSeedProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);

        try (PDDocument doc = Loader.loadPDF(file)) {
            TreeMap<String, Object> root = new TreeMap<>();
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            PDSignatureField sigField = null;
            if (form != null) {
                for (PDField f : form.getFieldTree()) {
                    if (f instanceof PDSignatureField) {
                        sigField = (PDSignatureField) f;
                        break;
                    }
                }
            }

            if (sigField == null) {
                root.put("field_present", false);
                out.print(jsonify(root));
                return;
            }
            root.put("field_present", true);

            // ---------- /Lock (read off COS — no upstream typed wrapper) ----------
            COSDictionary fieldDict = sigField.getCOSObject();
            COSBase lockBase = fieldDict.getDictionaryObject(COSName.getPDFName("Lock"));
            if (lockBase instanceof COSDictionary) {
                COSDictionary lock = (COSDictionary) lockBase;
                TreeMap<String, Object> lockMap = new TreeMap<>();
                COSName action = lock.getCOSName(COSName.getPDFName("Action"));
                if (action != null) {
                    lockMap.put("action", action.getName());
                }
                List<String> fields =
                        stringList(lock.getDictionaryObject(COSName.getPDFName("Fields")));
                if (fields != null) {
                    lockMap.put("fields", fields);
                }
                if (lock.containsKey(COSName.getPDFName("P"))) {
                    lockMap.put("p", lock.getInt(COSName.getPDFName("P")));
                }
                root.put("lock", lockMap);
            }

            // ---------- /SV seed value (typed accessors) ----------
            PDSeedValue sv = sigField.getSeedValue();
            if (sv != null) {
                TreeMap<String, Object> svMap = new TreeMap<>();
                if (sv.getFilter() != null) {
                    svMap.put("filter", sv.getFilter());
                }
                // getV() returns a primitive float; -1.0 signals "/V absent".
                svMap.put("v", (double) sv.getV());
                PDSeedValueMDP mdp = sv.getMDP();
                // getMDP() returns null when /MDP is absent; getP() returns -1
                // when /MDP exists but carries no /P entry.
                svMap.put("mdpP", mdp == null ? -1 : mdp.getP());
                svMap.put("addRevInfoReq", sv.isAddRevInfoRequired());
                root.put("sv", svMap);
            }

            out.print(jsonify(root));
        }
    }

    private static List<String> stringList(COSBase base) {
        if (!(base instanceof COSArray)) {
            return null;
        }
        COSArray arr = (COSArray) base;
        java.util.ArrayList<String> list = new java.util.ArrayList<>();
        for (int i = 0; i < arr.size(); i++) {
            COSBase item = arr.getObject(i);
            if (item instanceof COSString) {
                list.add(((COSString) item).getString());
            } else if (item instanceof COSName) {
                list.add(((COSName) item).getName());
            } else {
                list.add(String.valueOf(item));
            }
        }
        return list;
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
