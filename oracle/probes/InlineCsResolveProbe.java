import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.OperatorName;
import org.apache.pdfbox.contentstream.operator.OperatorProcessor;
import org.apache.pdfbox.contentstream.operator.state.Concatenate;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.contentstream.operator.state.SetMatrix;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;
import org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage;

/**
 * Live oracle probe: resolve the COLOUR SPACE of every inline image (BI/ID/EI)
 * on a page through Apache PDFBox's {@code PDInlineImage.getColorSpace()} and
 * emit the resolved colour-space identity WITHOUT rendering any raster.
 *
 * This isolates the abbreviated-key + abbreviated-colour-space + named-resource
 * resolution surface from the raster pixel path (covered by InlineImgProbe):
 * a wrong abbreviation expansion (/G, /RGB, /CMYK, /I) or a mis-resolved
 * named-resource /CS shows up here as the wrong colour-space class, component
 * count, or — for Indexed — the wrong base colour space, even when getImage()
 * happens to produce a plausible-looking grid.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> InlineCsResolveProbe input.pdf page
 * Output (UTF-8, to stdout), one line per inline image, in stream order:
 *   "<width> <height> <bpc> <stencil> <csName> <csClass> <nComp> <baseName> <baseComp>"
 * where:
 *   width/height/bpc = getWidth()/getHeight()/getBitsPerComponent()
 *   stencil          = isStencil() ("1"/"0")
 *   csName           = getColorSpace().getName()  (or "?" if resolution threw)
 *   csClass          = simple class name of the resolved PDColorSpace
 *   nComp            = getNumberOfComponents()
 *   baseName/baseComp= for PDIndexed, the base colour space name + comp count;
 *                      "-" / "-1" otherwise.
 */
public final class InlineCsResolveProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int pageIndex = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(pageIndex);
            List<String> lines = new ArrayList<>();
            ProbeEngine engine = new ProbeEngine();
            engine.addOperator(new Concatenate(engine));
            engine.addOperator(new Save(engine));
            engine.addOperator(new Restore(engine));
            engine.addOperator(new SetMatrix(engine));
            engine.addOperator(new CsCollector(engine, lines));
            engine.processPage(page);
            for (String line : lines) {
                out.println(line);
            }
        }
    }

    static final class ProbeEngine extends PDFStreamEngine {
    }

    static final class CsCollector extends OperatorProcessor {
        private final List<String> lines;

        CsCollector(PDFStreamEngine context, List<String> lines) {
            super(context);
            this.lines = lines;
        }

        @Override
        public String getName() {
            return OperatorName.BEGIN_INLINE_IMAGE;
        }

        @Override
        public void process(Operator operator, List<COSBase> operands)
                throws java.io.IOException {
            PDInlineImage image = new PDInlineImage(
                    operator.getImageParameters(),
                    operator.getImageData(),
                    getContext().getResources());
            lines.add(describe(image));
        }
    }

    static String describe(PDInlineImage image) {
        int width = image.getWidth();
        int height = image.getHeight();
        int bpc = image.getBitsPerComponent();
        String stencil = image.isStencil() ? "1" : "0";
        String csName = "?";
        String csClass = "?";
        int nComp = -1;
        String baseName = "-";
        int baseComp = -1;
        try {
            PDColorSpace cs = image.getColorSpace();
            csName = cs.getName();
            csClass = cs.getClass().getSimpleName();
            nComp = cs.getNumberOfComponents();
            if (cs instanceof PDIndexed) {
                PDColorSpace base = ((PDIndexed) cs).getBaseColorSpace();
                if (base != null) {
                    baseName = base.getName();
                    baseComp = base.getNumberOfComponents();
                }
            }
        } catch (Exception e) {
            csName = "?";
        }
        return width + " " + height + " " + bpc + " " + stencil + " "
                + csName + " " + csClass + " " + nComp + " "
                + baseName + " " + baseComp;
    }
}
