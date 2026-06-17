import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for AcroForm field FLATTENING.
 *
 * Three modes:
 *
 *   1. FLATTEN-ALL: java FlattenProbe flatten in.pdf out.pdf [name=value ...]
 *        Loads in.pdf, optionally sets the listed field values (which triggers
 *        upstream appearance regeneration), calls acroForm.flatten(), saves to
 *        out.pdf.
 *
 *   2. FLATTEN-SUBSET: java FlattenProbe flatten-subset in.pdf out.pdf fqName [name=value ...]
 *        Same as FLATTEN-ALL but flattens only the single field named by the
 *        first positional argument via acroForm.flatten(List.of(field), false).
 *        Any name=value pairs after it are applied first.
 *
 *   3. READ: java FlattenProbe read in.pdf
 *        Loads in.pdf and emits post-flatten facts, one fact per LF-terminated
 *        line:
 *
 *          ACROFORM\t<present 0/1>
 *          FIELDS\t<root /Fields count, 0 when no AcroForm>
 *          PAGES\t<page count>
 *          PAGE\t<index>\t<widget-annot count>\t<content-stream byte length>
 *          TEXT\t<extracted text, newlines -> \\n>
 *
 *        "widget-annot count" counts /Annots entries whose /Subtype is /Widget.
 *        "content-stream byte length" is the total decoded length of the page's
 *        /Contents (single stream or array of streams) — used to confirm the
 *        flatten append grew the stream.
 */
public final class FlattenProbe {
    private static final COSName WIDGET = COSName.getPDFName("Widget");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("flatten".equals(mode)) {
            doFlatten(args, false);
        } else if ("flatten-subset".equals(mode)) {
            doFlatten(args, true);
        } else if ("read".equals(mode)) {
            doRead(args, out);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doFlatten(String[] args, boolean subset) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            int firstPair = 3;
            String subsetName = null;
            if (subset) {
                subsetName = args[3];
                firstPair = 4;
            }
            for (int i = firstPair; i < args.length; i++) {
                int eq = args[i].indexOf('=');
                String name = args[i].substring(0, eq);
                String value = args[i].substring(eq + 1);
                PDField field = form.getField(name);
                if (field != null) {
                    field.setValue(value);
                }
            }
            if (subset) {
                List<PDField> only = new ArrayList<>();
                PDField field = form.getField(subsetName);
                if (field != null) {
                    only.add(field);
                }
                form.flatten(only, false);
            } else {
                form.flatten();
            }
            doc.save(outFile);
        }
    }

    private static void doRead(String[] args, PrintStream out) throws Exception {
        File in = new File(args[1]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            StringBuilder sb = new StringBuilder();
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            boolean hasForm = form != null;
            sb.append("ACROFORM\t").append(hasForm ? "1" : "0").append('\n');

            int fieldCount = 0;
            if (hasForm) {
                COSBase fields = form.getCOSObject().getDictionaryObject(COSName.FIELDS);
                if (fields instanceof COSArray) {
                    fieldCount = ((COSArray) fields).size();
                }
            }
            sb.append("FIELDS\t").append(fieldCount).append('\n');

            int pageCount = doc.getNumberOfPages();
            sb.append("PAGES\t").append(pageCount).append('\n');

            for (int p = 0; p < pageCount; p++) {
                PDPage page = doc.getPage(p);
                int widgets = countWidgets(page.getCOSObject());
                long contentLen = contentLength(page.getCOSObject());
                sb.append("PAGE\t").append(p).append('\t')
                        .append(widgets).append('\t').append(contentLen).append('\n');
            }

            String text = new PDFTextStripper().getText(doc);
            sb.append("TEXT\t").append(esc(text)).append('\n');
            out.print(sb);
        }
    }

    private static int countWidgets(COSDictionary pageDict) {
        COSBase annots = pageDict.getDictionaryObject(COSName.ANNOTS);
        if (!(annots instanceof COSArray)) {
            return 0;
        }
        int count = 0;
        COSArray arr = (COSArray) annots;
        for (int i = 0; i < arr.size(); i++) {
            COSBase entry = arr.getObject(i);
            if (entry instanceof COSDictionary) {
                COSBase sub = ((COSDictionary) entry).getDictionaryObject(COSName.SUBTYPE);
                if (WIDGET.equals(sub)) {
                    count++;
                }
            }
        }
        return count;
    }

    private static long contentLength(COSDictionary pageDict) throws Exception {
        COSBase contents = pageDict.getDictionaryObject(COSName.CONTENTS);
        long total = 0;
        if (contents instanceof COSStream) {
            total += streamLen((COSStream) contents);
        } else if (contents instanceof COSArray) {
            COSArray arr = (COSArray) contents;
            for (int i = 0; i < arr.size(); i++) {
                COSBase entry = arr.getObject(i);
                if (entry instanceof COSStream) {
                    total += streamLen((COSStream) entry);
                }
            }
        }
        return total;
    }

    private static long streamLen(COSStream stream) throws Exception {
        long len = 0;
        try (var in = stream.createInputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                len += n;
            }
        }
        return len;
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
