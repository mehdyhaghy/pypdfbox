import java.io.File;
import java.io.PrintStream;
import java.util.List;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDSignatureField;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSeedValue;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;

/**
 * Live oracle probe: signature-field metadata + visible appearance.
 *
 * For the first /FT /Sig field of the AcroForm, emits a fixed-shape block:
 *   field.present=<true|false>
 *   field.ft=<Sig|...>
 *   lock.present=<true|false>
 *   lock.action=<All|Include|Exclude|>
 *   lock.fields=<comma-joined>
 *   sv.present=<true|false>
 *   sv.subfilter=<comma-joined>
 *   sv.digestmethod=<comma-joined>
 *   sv.reasons=<pipe-joined>
 *   sv.subfilterReq=<true|false>
 *   sv.reasonReq=<true|false>
 *   sv.digestReq=<true|false>
 *   sv.ff=<int>
 *   widget.hasAPN=<true|false>
 *   sig.present=<true|false>
 *   sig.subfilter=<value|>
 *
 * PDFBox 3.0.7 PDSeedValue does not expose typed required-flag getters for
 * every constraint, so the /Ff integer is read straight off the COS
 * dictionary and the bits decoded here (PDF 32000-1 Table 234). This keeps
 * the oracle independent of PDFBox's accessor surface — it reports the raw
 * spec-defined facts pypdfbox's typed accessors must reproduce.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SigFieldProbe doc.pdf
 */
public final class SigFieldProbe {

    // /Ff required-flag bits (PDF 32000-1 Table 234).
    private static final int FLAG_FILTER = 1 << 0;
    private static final int FLAG_SUBFILTER = 1 << 1;
    private static final int FLAG_REASON = 1 << 3;
    private static final int FLAG_DIGEST_METHOD = 1 << 6;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);

        try (PDDocument doc = Loader.loadPDF(file)) {
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            // The metadata block (/FT, /Lock, /SV, widget appearance) is read
            // from the FIRST signature field. The /V block is read from the
            // first signature field that actually carries a /V signature —
            // PDDocument.addSignature appends a fresh field, so the signed
            // field is not necessarily the first one in tree order.
            PDSignatureField sigField = null;
            PDSignatureField signedField = null;
            if (form != null) {
                for (PDField f : form.getFieldTree()) {
                    if (f instanceof PDSignatureField) {
                        PDSignatureField sf = (PDSignatureField) f;
                        if (sigField == null) {
                            sigField = sf;
                        }
                        if (signedField == null && sf.getSignature() != null) {
                            signedField = sf;
                        }
                    }
                }
            }

            if (sigField == null) {
                out.println("field.present=false");
                return;
            }
            out.println("field.present=true");
            out.println("field.ft=" + str(sigField.getFieldType()));

            // ---------- /Lock ----------
            COSDictionary fieldDict = sigField.getCOSObject();
            COSBase lockBase = fieldDict.getDictionaryObject(COSName.getPDFName("Lock"));
            if (lockBase instanceof COSDictionary) {
                COSDictionary lock = (COSDictionary) lockBase;
                out.println("lock.present=true");
                COSName action = lock.getCOSName(COSName.getPDFName("Action"));
                out.println("lock.action=" + (action == null ? "" : action.getName()));
                out.println("lock.fields=" + joinStrings(
                        lock.getDictionaryObject(COSName.getPDFName("Fields")), ","));
            } else {
                out.println("lock.present=false");
                out.println("lock.action=");
                out.println("lock.fields=");
            }

            // ---------- /SV seed value ----------
            PDSeedValue sv = sigField.getSeedValue();
            COSBase svBase = fieldDict.getDictionaryObject(COSName.getPDFName("SV"));
            if (sv != null && svBase instanceof COSDictionary) {
                COSDictionary svDict = (COSDictionary) svBase;
                out.println("sv.present=true");
                out.println("sv.subfilter=" + join(sv.getSubFilter(), ","));
                out.println("sv.digestmethod=" + join(sv.getDigestMethod(), ","));
                // /Reasons is read straight off the COS array as text strings
                // (PDF 32000-1 Table 234: "array of text strings"). PDFBox
                // 3.0.7's PDSeedValue.getReasons() calls toCOSNameStringList()
                // and throws ClassCastException on the COSString entries its
                // own setReasons() wrote — a confirmed upstream bug — so the
                // oracle reports the spec-correct fact directly.
                out.println("sv.reasons=" + joinStrings(
                        svDict.getDictionaryObject(COSName.getPDFName("Reasons")), "|"));
                int ff = svDict.getInt(COSName.FF, 0);
                out.println("sv.subfilterReq=" + ((ff & FLAG_SUBFILTER) != 0));
                out.println("sv.reasonReq=" + ((ff & FLAG_REASON) != 0));
                out.println("sv.digestReq=" + ((ff & FLAG_DIGEST_METHOD) != 0));
                out.println("sv.filterReq=" + ((ff & FLAG_FILTER) != 0));
                out.println("sv.ff=" + ff);
            } else {
                out.println("sv.present=false");
                out.println("sv.subfilter=");
                out.println("sv.digestmethod=");
                out.println("sv.reasons=");
                out.println("sv.subfilterReq=false");
                out.println("sv.reasonReq=false");
                out.println("sv.digestReq=false");
                out.println("sv.filterReq=false");
                out.println("sv.ff=0");
            }

            // ---------- widget /AP /N ----------
            boolean hasApn = false;
            List<PDAnnotationWidget> widgets = sigField.getWidgets();
            if (widgets != null && !widgets.isEmpty()) {
                PDAnnotationWidget widget = widgets.get(0);
                PDAppearanceDictionary ap = widget.getAppearance();
                hasApn = ap != null && ap.getNormalAppearance() != null;
            }
            out.println("widget.hasAPN=" + hasApn);

            // ---------- /V signature ----------
            PDSignature sig = signedField != null ? signedField.getSignature() : null;
            if (sig != null) {
                out.println("sig.present=true");
                out.println("sig.subfilter=" + str(sig.getSubFilter()));
            } else {
                out.println("sig.present=false");
                out.println("sig.subfilter=");
            }
        }
    }

    private static String str(String s) {
        return s == null ? "" : s;
    }

    private static String join(List<String> values, String sep) {
        if (values == null || values.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) {
                sb.append(sep);
            }
            sb.append(values.get(i));
        }
        return sb.toString();
    }

    private static String joinStrings(COSBase base, String sep) {
        if (!(base instanceof COSArray)) {
            return "";
        }
        COSArray arr = (COSArray) base;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < arr.size(); i++) {
            COSBase item = arr.getObject(i);
            String v;
            if (item instanceof COSString) {
                v = ((COSString) item).getString();
            } else if (item instanceof COSName) {
                v = ((COSName) item).getName();
            } else if (item instanceof COSInteger) {
                v = Long.toString(((COSInteger) item).longValue());
            } else {
                v = String.valueOf(item);
            }
            if (i > 0) {
                sb.append(sep);
            }
            sb.append(v);
        }
        return sb.toString();
    }
}
