import java.io.ByteArrayInputStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroup;
import org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroupAttributes;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the model-layer PDXObject factory + PDFormXObject /
 * PDTransparencyGroupAttributes accessors. Emits flat key=value lines.
 */
public final class FormXObjectModelProbe {

    static COSStream formStream(PDDocument doc) {
        COSStream s = doc.getDocument().createCOSStream();
        s.setItem(COSName.SUBTYPE, COSName.FORM);
        return s;
    }

    public static void main(String[] args) throws Exception {
        StringBuilder out = new StringBuilder();
        try (PDDocument doc = new PDDocument()) {

            // --- write-side fresh construction dict shape ---
            PDFormXObject fresh = new PDFormXObject(doc);
            COSDictionary fd = fresh.getCOSObject();
            out.append("fresh.Type=").append(fd.getNameAsString(COSName.TYPE)).append("\n");
            out.append("fresh.Subtype=").append(fd.getNameAsString(COSName.SUBTYPE)).append("\n");
            out.append("fresh.FormType=").append(fresh.getFormType()).append("\n");
            out.append("fresh.BBox=").append(fresh.getBBox()).append("\n");
            out.append("fresh.Resources=").append(fresh.getResources()).append("\n");
            out.append("fresh.StructParents=").append(fresh.getStructParents()).append("\n");
            // round-trip bbox + matrix
            fresh.setBBox(new PDRectangle(1, 2, 3, 4));
            COSArray bb = fresh.getCOSObject().getCOSArray(COSName.BBOX);
            out.append("fresh.bboxRoundTrip=").append(bb).append("\n");

            // --- factory dispatch on Form (no group) ---
            COSStream s1 = formStream(doc);
            PDXObject o1 = PDXObject.createXObject(s1, null);
            out.append("dispatch.form.class=").append(o1.getClass().getSimpleName()).append("\n");

            // Form with /Group /S /Transparency -> PDTransparencyGroup
            COSStream s2 = formStream(doc);
            COSDictionary grp = new COSDictionary();
            grp.setItem(COSName.S, COSName.TRANSPARENCY);
            s2.setItem(COSName.GROUP, grp);
            PDXObject o2 = PDXObject.createXObject(s2, null);
            out.append("dispatch.tgroup.class=").append(o2.getClass().getSimpleName()).append("\n");

            // Form with /Group but /S not transparency -> plain PDFormXObject
            COSStream s3 = formStream(doc);
            COSDictionary grp3 = new COSDictionary();
            grp3.setItem(COSName.S, COSName.getPDFName("Foo"));
            s3.setItem(COSName.GROUP, grp3);
            PDXObject o3 = PDXObject.createXObject(s3, null);
            out.append("dispatch.groupNonTransparency.class=").append(o3.getClass().getSimpleName()).append("\n");

            // unknown subtype
            COSStream s4 = doc.getDocument().createCOSStream();
            s4.setItem(COSName.SUBTYPE, COSName.getPDFName("Bogus"));
            try {
                PDXObject.createXObject(s4, null);
                out.append("dispatch.unknown=NOEXC\n");
            } catch (Exception e) {
                out.append("dispatch.unknown.msg=").append(e.getMessage()).append("\n");
            }

            // missing subtype
            COSStream s5 = doc.getDocument().createCOSStream();
            try {
                PDXObject.createXObject(s5, null);
                out.append("dispatch.missing=NOEXC\n");
            } catch (Exception e) {
                out.append("dispatch.missing.msg=").append(e.getMessage()).append("\n");
            }

            // non-stream base
            try {
                PDXObject.createXObject(new COSDictionary(), null);
                out.append("dispatch.nonstream=NOEXC\n");
            } catch (Exception e) {
                out.append("dispatch.nonstream.msg=").append(e.getMessage()).append("\n");
            }

            // null base
            out.append("dispatch.null=").append(PDXObject.createXObject(null, null)).append("\n");

            // --- getMatrix default identity (no /Matrix) ---
            PDFormXObject pf = new PDFormXObject(formStream(doc));
            Matrix m = pf.getMatrix();
            out.append("matrix.default=").append(m.toString()).append("\n");

            // getMatrix malformed: array of size 4 -> identity
            COSStream sm = formStream(doc);
            COSArray short4 = new COSArray();
            for (int i = 0; i < 4; i++) short4.add(new COSFloat(2.0f));
            sm.setItem(COSName.MATRIX, short4);
            out.append("matrix.short4=").append(new PDFormXObject(sm).getMatrix().toString()).append("\n");

            // getMatrix non-numeric entry -> identity
            COSStream sm2 = formStream(doc);
            COSArray bad = new COSArray();
            for (int i = 0; i < 5; i++) bad.add(new COSFloat(1.0f));
            bad.add(COSName.getPDFName("X"));
            sm2.setItem(COSName.MATRIX, bad);
            out.append("matrix.nonNumeric=").append(new PDFormXObject(sm2).getMatrix().toString()).append("\n");

            // --- getResources: key present but not a dict (broken self-ref) ---
            COSStream sr = formStream(doc);
            sr.setItem(COSName.RESOURCES, COSInteger.get(5));
            PDResources rr = new PDFormXObject(sr).getResources();
            out.append("resources.brokenNotDict=").append(rr == null ? "null" : rr.getClass().getSimpleName()).append("\n");

            // --- getBBox malformed (not an array) ---
            COSStream sb = formStream(doc);
            sb.setItem(COSName.BBOX, COSInteger.get(7));
            out.append("bbox.nonArray=").append(new PDFormXObject(sb).getBBox()).append("\n");

            // --- transparency group attributes defaults ---
            PDTransparencyGroupAttributes tga = new PDTransparencyGroupAttributes();
            out.append("tga.default.S=").append(tga.getCOSObject().getNameAsString(COSName.S)).append("\n");
            out.append("tga.default.isolated=").append(tga.isIsolated()).append("\n");
            out.append("tga.default.knockout=").append(tga.isKnockout()).append("\n");
            out.append("tga.default.colorSpace=").append(tga.getColorSpace()).append("\n");

            // empty dict tga (no /S)
            PDTransparencyGroupAttributes tga2 = new PDTransparencyGroupAttributes(new COSDictionary());
            out.append("tga.empty.colorSpace=").append(tga2.getColorSpace()).append("\n");
            out.append("tga.empty.isolated=").append(tga2.isIsolated()).append("\n");

            // --- PDFormXObject.getGroup() (typed) ---
            PDFormXObject noGroup = new PDFormXObject(formStream(doc));
            out.append("form.getGroup.noGroup=").append(noGroup.getGroup()).append("\n");
        }
        System.out.print(out);
    }
}
