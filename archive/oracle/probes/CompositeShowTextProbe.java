import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.text.BeginText;
import org.apache.pdfbox.contentstream.operator.text.EndText;
import org.apache.pdfbox.contentstream.operator.state.SetMatrix;
import org.apache.pdfbox.contentstream.operator.text.MoveText;
import org.apache.pdfbox.contentstream.operator.text.SetFontAndSize;
import org.apache.pdfbox.contentstream.operator.text.ShowText;
import org.apache.pdfbox.contentstream.operator.text.ShowTextAdjusted;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.util.Matrix;
import org.apache.pdfbox.util.Vector;

/**
 * Live oracle probe: composite (Type0 / CID) font show-text byte to code
 * chunking through the content-stream engine.
 *
 * Usage:
 *   java CompositeShowTextProbe <ttf-path> <out.pdf>
 *
 * Builds a one-page PDF whose font is an Identity-H Type0 font embedded
 * from the supplied TrueType program (PDType0Font.load(doc, ttf, true)).
 * The content stream shows a fixed run of multi-byte (2-byte) codes via a
 * Tj string plus a TJ array, so the engine must split the byte string into
 * 2-byte codes through the font's /Encoding (Identity-H) codespace, then
 * dispatch one showGlyph per code with the correct CID + displacement.
 *
 * The exact glyph bytes are not known up front (they are the embedded
 * font's GIDs for the chosen text), so the probe lets PDFBox encode a
 * known ASCII string and writes those bytes into the content stream
 * (PDPageContentStream.showText). The differential test reads the SAME
 * saved PDF, so pypdfbox decodes the identical bytes.
 *
 * For each glyph delivered to showGlyph(Matrix trm, PDFont, int code,
 * Vector displacement) the probe emits one canonical tab-separated line:
 *
 *   code \t cid \t dispX \t trmE \t trmF
 *
 * code is the multi-byte character code the encoding CMap chunked out;
 * cid is PDType0Font.codeToCID(code); dispX is displacement.getX() (the
 * horizontal advance in em units); trmE / trmF are the glyph origin in
 * user space (so the per-code advance accumulation is observable). Floats
 * are %.4f, Locale.ROOT. Output is UTF-8 to stdout, no framing.
 */
public final class CompositeShowTextProbe {
    public static void main(String[] args) throws Exception {
        final PrintStream out = new PrintStream(System.out, true, "UTF-8");
        final File ttfFile = new File(args[0]);
        final File outFile = new File(args[1]);

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 400, 400));
            doc.addPage(page);
            PDFont font = PDType0Font.load(doc, ttfFile);
            PDResources resources = new PDResources();
            COSName fontName = resources.add(font);
            if (!"F1".equals(fontName.getName())) {
                resources.put(COSName.getPDFName("F1"),
                        resources.getFont(fontName));
            }
            page.setResources(resources);

            // Build the content stream with two show-text runs. The font's
            // encode() turns each ASCII char into a 2-byte Identity-H code,
            // exercising the multi-byte codespace chunking.
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            PrintStream cs = new PrintStream(buf, true, "US-ASCII");
            cs.print("BT\n/F1 12 Tf\n1 0 0 1 50 350 Tm\n");
            // Tj run.
            cs.print("(");
            buf.write(escape(font.encode("Hi Wax")));
            cs.print(") Tj\n");
            // TJ run with a numeric adjustment between the two codes.
            cs.print("[(");
            buf.write(escape(font.encode("Ay")));
            cs.print(") -250 (");
            buf.write(escape(font.encode("Vo")));
            cs.print(")] TJ\n");
            cs.print("ET\n");
            cs.flush();

            // Write the content stream directly (we already hand-built the
            // raw bytes including the encoded glyph codes).
            PDStream contents = new PDStream(doc,
                    new ByteArrayInputStream(buf.toByteArray()));
            page.setContents(contents);
            doc.save(outFile);
        }

        final StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(outFile)) {
            PDPage page = doc.getPage(0);
            PDFStreamEngine engine = new PDFStreamEngine() {
                @Override
                protected void showGlyph(Matrix trm, PDFont fnt, int code,
                        Vector displacement) throws java.io.IOException {
                    int cid = code;
                    if (fnt instanceof PDType0Font) {
                        cid = ((PDType0Font) fnt).codeToCID(code);
                    }
                    sb.append(String.format(
                            Locale.ROOT,
                            "%d\t%d\t%.4f\t%.4f\t%.4f%n",
                            code, cid,
                            displacement.getX(),
                            trm.getTranslateX(), trm.getTranslateY()));
                    super.showGlyph(trm, fnt, code, displacement);
                }
            };
            engine.addOperator(new BeginText(engine));
            engine.addOperator(new EndText(engine));
            engine.addOperator(new SetFontAndSize(engine));
            engine.addOperator(new SetMatrix(engine));
            engine.addOperator(new MoveText(engine));
            engine.addOperator(new ShowText(engine));
            engine.addOperator(new ShowTextAdjusted(engine));
            engine.processPage(page);
        }
        out.print(sb);
    }

    /** PDF literal-string escaping for raw glyph-code bytes. */
    private static byte[] escape(byte[] data) {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        for (byte raw : data) {
            int c = raw & 0xFF;
            if (c == '(' || c == ')' || c == '\\') {
                b.write('\\');
            }
            b.write(c);
        }
        return b.toByteArray();
    }
}
