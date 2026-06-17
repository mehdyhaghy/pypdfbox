import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for NON-FORM annotation behaviour under an AcroForm
 * FLATTEN. The high-value question: does {@code PDAcroForm.flatten()} touch
 * markup / stamp / free-text annotations, or is it form-field (Widget) only?
 *
 * Modes:
 *
 *   1. FLATTEN: java AnnotFlattenProbe flatten in.pdf out.pdf
 *        Loads in.pdf, calls catalog.getAcroForm().flatten() (form-field
 *        flatten only — no annotation flatten is invoked), saves to out.pdf.
 *
 *   2. READ: java AnnotFlattenProbe read in.pdf
 *        Loads in.pdf and emits, one fact per LF-terminated line:
 *
 *          ACROFORM\t<present 0/1>
 *          FIELDS\t<root /Fields count, 0 when no AcroForm>
 *          PAGES\t<page count>
 *          PAGE\t<index>\t<total /Annots count>
 *          SUB\t<index>\t<subtype name>\t<count on that page>
 *
 *        SUB lines are emitted once per distinct /Subtype seen on the page,
 *        in first-seen order, so a test can assert which annotation subtypes
 *        survive a flatten and at what multiplicity.
 *
 *   3. RENDER: java AnnotFlattenProbe render in.pdf pageIndex
 *        Emits the same 16x16 average-luminance grid fingerprint as
 *        RenderProbe (line 1 "<w> <h>", line 2 = 256 ints) at 72 DPI, so the
 *        visible result of a flatten can be compared before/after and
 *        cross-engine.
 */
public final class AnnotFlattenProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("flatten".equals(mode)) {
            doFlatten(args);
        } else if ("read".equals(mode)) {
            doRead(args, out);
        } else if ("render".equals(mode)) {
            doRender(args, out);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doFlatten(String[] args) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            if (form != null) {
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
                COSBase annotsBase = page.getCOSObject().getDictionaryObject(COSName.ANNOTS);
                int total = 0;
                // First-seen-ordered subtype tallies (no java.util import churn
                // beyond arrays — small fixed cardinality).
                java.util.LinkedHashMap<String, Integer> tally = new java.util.LinkedHashMap<>();
                if (annotsBase instanceof COSArray) {
                    COSArray arr = (COSArray) annotsBase;
                    total = arr.size();
                    for (int i = 0; i < arr.size(); i++) {
                        COSBase entry = arr.getObject(i);
                        String sub = "?";
                        if (entry instanceof COSDictionary) {
                            COSBase st = ((COSDictionary) entry)
                                    .getDictionaryObject(COSName.SUBTYPE);
                            if (st instanceof COSName) {
                                sub = ((COSName) st).getName();
                            }
                        }
                        tally.merge(sub, 1, Integer::sum);
                    }
                }
                sb.append("PAGE\t").append(p).append('\t').append(total).append('\n');
                for (java.util.Map.Entry<String, Integer> e : tally.entrySet()) {
                    sb.append("SUB\t").append(p).append('\t')
                            .append(e.getKey()).append('\t').append(e.getValue()).append('\n');
                }
            }
            out.print(sb);
        }
    }

    private static void doRender(String[] args, PrintStream out) throws Exception {
        File in = new File(args[1]);
        int page = Integer.parseInt(args[2]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(page, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);

            long[] sum = new long[GRID * GRID];
            long[] cnt = new long[GRID * GRID];
            for (int y = 0; y < h; y++) {
                int cy = (int) ((long) y * GRID / h);
                if (cy >= GRID) {
                    cy = GRID - 1;
                }
                for (int x = 0; x < w; x++) {
                    int cx = (int) ((long) x * GRID / w);
                    if (cx >= GRID) {
                        cx = GRID - 1;
                    }
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    int lum = (int) Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                    int idx = cy * GRID + cx;
                    sum[idx] += lum;
                    cnt[idx] += 1;
                }
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < GRID * GRID; i++) {
                if (i > 0) {
                    sb.append(' ');
                }
                long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
                sb.append(avg);
            }
            out.println(sb.toString());
        }
    }
}
