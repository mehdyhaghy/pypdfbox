import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.DrawObject;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;

/**
 * Live oracle probe: PDFStreamEngine form-XObject "Do" recursion guard.
 *
 * Upstream PDFBox 3.0.7 (DrawObject.process) caps recursion by depth: it calls
 * increaseLevel() before drawing a form XObject, and if getLevel() > 50 it logs
 * "recursion is too deep, skipping form XObject" and returns without recursing.
 * There is no infinite loop for a self-referencing form or a 2-form cycle — the
 * depth cap terminates dispatch at a finite, deterministic operator count.
 *
 * This probe builds two PDFs:
 *   - args[0]: one page whose form XObject SELF references (its content stream
 *     ends with "/Self Do"), so each draw re-enters Do until the level cap.
 *   - args[1] is derived in-process: a 2-form cycle (FormA's Do -> FormB,
 *     FormB's Do -> FormA).
 *
 * For each, it drives a counting PDFStreamEngine (DrawObject registered, every
 * dispatched operator counted) over the page and emits the finite total
 * operator count. pypdfbox drives the identical saved bytes through its own
 * PDFStreamEngine and asserts the same finite counts (proving termination +
 * byte/behaviour parity of the guard).
 *
 * Canonical output (UTF-8), two lines:
 *   SELF <count>
 *   CYCLE <count>
 */
public final class FormRecursionGuardProbe {

    /** Engine that counts every dispatched operator and draws form XObjects. */
    static final class CountingEngine extends PDFStreamEngine {
        long count = 0;

        CountingEngine() {
            addOperator(new DrawObject(this));
        }

        @Override
        protected void processOperator(Operator operator, List<COSBase> operands)
                throws java.io.IOException {
            count++;
            super.processOperator(operator, operands);
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        File selfFile = new File(args[0]);
        buildSelfReferencing(selfFile);
        long selfCount;
        try (PDDocument doc = Loader.loadPDF(selfFile)) {
            CountingEngine engine = new CountingEngine();
            engine.processPage(doc.getPage(0));
            selfCount = engine.count;
        }

        File cycleFile = new File(args[1]);
        buildTwoFormCycle(cycleFile);
        long cycleCount;
        try (PDDocument doc = Loader.loadPDF(cycleFile)) {
            CountingEngine engine = new CountingEngine();
            engine.processPage(doc.getPage(0));
            cycleCount = engine.count;
        }

        out.println("SELF " + selfCount);
        out.println("CYCLE " + cycleCount);
    }

    /** One page; page content draws /Self; /Self's content draws /Self. */
    static void buildSelfReferencing(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);

            PDFormXObject form = newForm(doc);
            // Form's content stream invokes itself.
            writeStream(form.getCOSObject(), "/Self Do\n");
            PDResources formRes = new PDResources();
            formRes.put(COSName.getPDFName("Self"), form);
            form.setResources(formRes);

            // Page content draws the form once.
            PDResources pageRes = new PDResources();
            pageRes.put(COSName.getPDFName("Self"), form);
            page.setResources(pageRes);
            writePageContent(doc, page, "/Self Do\n");

            doc.save(file);
        }
    }

    /** One page; FormA -> FormB -> FormA cycle. */
    static void buildTwoFormCycle(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);

            PDFormXObject formA = newForm(doc);
            PDFormXObject formB = newForm(doc);

            writeStream(formA.getCOSObject(), "/Fb Do\n");
            PDResources resA = new PDResources();
            resA.put(COSName.getPDFName("Fb"), formB);
            formA.setResources(resA);

            writeStream(formB.getCOSObject(), "/Fa Do\n");
            PDResources resB = new PDResources();
            resB.put(COSName.getPDFName("Fa"), formA);
            formB.setResources(resB);

            PDResources pageRes = new PDResources();
            pageRes.put(COSName.getPDFName("Fa"), formA);
            page.setResources(pageRes);
            writePageContent(doc, page, "/Fa Do\n");

            doc.save(file);
        }
    }

    static PDFormXObject newForm(PDDocument doc) {
        PDStream stream = new PDStream(doc);
        PDFormXObject form = new PDFormXObject(stream);
        form.setBBox(new PDRectangle(0, 0, 100, 100));
        form.setResources(new PDResources());
        return form;
    }

    static void writeStream(COSStream cos, String content) throws Exception {
        try (java.io.OutputStream os = cos.createOutputStream()) {
            os.write(content.getBytes("US-ASCII"));
        }
    }

    static void writePageContent(PDDocument doc, PDPage page, String content)
            throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        baos.write(content.getBytes("US-ASCII"));
        PDStream contents = new PDStream(doc);
        try (java.io.OutputStream os = contents.createOutputStream()) {
            os.write(baos.toByteArray());
        }
        page.setContents(contents);
    }

    private FormRecursionGuardProbe() {}
}
