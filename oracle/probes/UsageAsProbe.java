import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;

/**
 * Live oracle probe: dump Apache PDFBox's view of the /OCProperties /D /AS
 * Usage Application array (PDF 32000-1 §8.11.4.4 Table 102) plus per-OCG
 * /Usage /View /ViewState and the public isGroupEnabled() resolution.
 *
 * PDFBox 3.0 ships NO public accessor for the /AS array — callers must walk
 * the COS dict themselves (mirroring pypdfbox's
 * PDOptionalContentConfiguration.get_as_array). PDFBox's isGroupEnabled does
 * NOT factor /AS into the answer either (the public surface checks only the
 * /D /ON + /D /OFF lists against the BaseState seed); this probe exposes both
 * facts so the differential test can assert pypdfbox agrees on each.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> UsageAsProbe input.pdf
 * Output (UTF-8, one fact per line, canonical order):
 *   AS_LEN=<n>
 *   AS entry=<i> event=<E> categories=<C1|C2|...> ocgs=<n>
 *     (one per /AS entry, in array order)
 *   OCG name=<n> enabled=<true|false> view=<ON|OFF|none>
 *     (one per OCG, sorted by name; enabled = isGroupEnabled)
 * When the catalog has no /OCProperties: the single line NO_OCPROPERTIES.
 */
public final class UsageAsProbe {

    private static COSDictionary asDict(COSBase base) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        if (base instanceof COSDictionary) {
            return (COSDictionary) base;
        }
        return null;
    }

    private static COSArray asArray(COSBase base) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        if (base instanceof COSArray) {
            return (COSArray) base;
        }
        return null;
    }

    /** Resolve /Category to a pipe-joined list of names. The spec allows a
     *  single name OR an array of names; both shapes flatten to the same
     *  pipe-joined string here (sorted lexicographically so the test only
     *  asserts on set-equivalence, not array order). */
    private static String categories(COSDictionary entry) {
        COSBase raw = entry.getDictionaryObject(COSName.getPDFName("Category"));
        if (raw instanceof COSObject) {
            raw = ((COSObject) raw).getObject();
        }
        List<String> names = new ArrayList<>();
        if (raw instanceof COSName) {
            names.add(((COSName) raw).getName());
        } else if (raw instanceof COSArray) {
            COSArray arr = (COSArray) raw;
            for (int i = 0; i < arr.size(); i++) {
                COSBase v = arr.getObject(i);
                if (v instanceof COSName) {
                    names.add(((COSName) v).getName());
                }
            }
        }
        Collections.sort(names);
        return String.join("|", names);
    }

    /** /Usage /View /ViewState for an OCG dict, or "none". */
    private static String viewState(PDOptionalContentGroup g) {
        COSDictionary usage = g.getCOSObject().getCOSDictionary(
                COSName.getPDFName("Usage"));
        if (usage == null) {
            return "none";
        }
        COSDictionary view = usage.getCOSDictionary(COSName.getPDFName("View"));
        if (view == null) {
            return "none";
        }
        COSName state = (COSName) view.getDictionaryObject(
                COSName.getPDFName("ViewState"));
        return state == null ? "none" : state.getName().toUpperCase();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDOptionalContentProperties ocp = catalog.getOCProperties();
            if (ocp == null) {
                out.println("NO_OCPROPERTIES");
                return;
            }

            COSDictionary d = ocp.getCOSObject().getCOSDictionary(
                    COSName.getPDFName("D"));
            COSArray asArr = d == null
                    ? null
                    : d.getCOSArray(COSName.getPDFName("AS"));
            int asLen = asArr == null ? 0 : asArr.size();
            out.println("AS_LEN=" + asLen);

            if (asArr != null) {
                for (int i = 0; i < asArr.size(); i++) {
                    COSDictionary entry = asDict(asArr.getObject(i));
                    if (entry == null) {
                        out.println("AS entry=" + i + " event= categories= ocgs=0");
                        continue;
                    }
                    COSName eventName = (COSName) entry.getDictionaryObject(
                            COSName.getPDFName("Event"));
                    String event = eventName == null ? "" : eventName.getName();
                    String cats = categories(entry);
                    COSArray ocgs = entry.getCOSArray(COSName.getPDFName("OCGs"));
                    int ocgsCount = 0;
                    if (ocgs != null) {
                        for (int j = 0; j < ocgs.size(); j++) {
                            if (asDict(ocgs.getObject(j)) != null) {
                                ocgsCount++;
                            }
                        }
                    }
                    out.println("AS entry=" + i
                            + " event=" + event
                            + " categories=" + cats
                            + " ocgs=" + ocgsCount);
                }
            }

            List<String> ocgLines = new ArrayList<>();
            for (PDOptionalContentGroup g : ocp.getOptionalContentGroups()) {
                String name = g.getName();
                boolean enabled = ocp.isGroupEnabled(g);
                ocgLines.add("OCG name=" + (name == null ? "" : name)
                        + " enabled=" + enabled
                        + " view=" + viewState(g));
            }
            Collections.sort(ocgLines);
            for (String line : ocgLines) {
                out.println(line);
            }
        }
    }
}
