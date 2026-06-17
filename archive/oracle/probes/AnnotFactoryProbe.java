import java.util.Map;
import java.util.TreeMap;

import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCaret;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationHighlight;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPopup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationRubberStamp;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSound;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquare;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquiggly;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationStrikeout;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationUnderline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;

/**
 * Differential probe for the PDAnnotation factory + per-subtype no-arg
 * constructor dict shape.
 *
 * <p>Mode {@code ctor}: print, for each no-arg constructor, the sorted set of
 * keys it seeds (with values for the small set of non-name seeds), so pypdfbox
 * can assert the same shape.</p>
 *
 * <p>Mode {@code dispatch}: print the simple class name that
 * {@code createAnnotation} returns for a /Subtype stored as a COSName, a
 * COSString, and for a missing /Subtype.</p>
 */
public final class AnnotFactoryProbe
{
    private AnnotFactoryProbe()
    {
    }

    private static String shape(PDAnnotation a)
    {
        COSDictionary d = a.getCOSObject();
        TreeMap<String, String> m = new TreeMap<>();
        for (COSName k : d.keySet())
        {
            COSBase v = d.getItem(k);
            String name = k.getName();
            if ("Type".equals(name) || "Subtype".equals(name))
            {
                m.put(name, ((COSName) v).getName());
            }
            else if (v instanceof COSArray)
            {
                m.put(name, "array[" + ((COSArray) v).size() + "]");
            }
            else
            {
                m.put(name, v == null ? "null" : v.getClass().getSimpleName());
            }
        }
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, String> e : m.entrySet())
        {
            if (sb.length() > 0)
            {
                sb.append(",");
            }
            sb.append(e.getKey()).append("=").append(e.getValue());
        }
        return sb.toString();
    }

    private static void ctor(String name, PDAnnotation a)
    {
        System.out.println(name + "|" + shape(a));
    }

    public static void main(String[] args) throws Exception
    {
        String mode = args.length > 0 ? args[0] : "ctor";
        if ("dispatch".equals(mode))
        {
            COSDictionary cosName = new COSDictionary();
            cosName.setItem(COSName.SUBTYPE, COSName.getPDFName("Link"));
            System.out.println("cosname=" + PDAnnotation.createAnnotation(cosName)
                    .getClass().getSimpleName());

            COSDictionary cosStr = new COSDictionary();
            cosStr.setItem(COSName.SUBTYPE, new COSString("Link"));
            PDAnnotation a = PDAnnotation.createAnnotation(cosStr);
            System.out.println("cosstring=" + a.getClass().getSimpleName());
            System.out.println("cosstring_subtype=" + a.getSubtype());

            COSDictionary none = new COSDictionary();
            System.out.println("missing=" + PDAnnotation.createAnnotation(none)
                    .getClass().getSimpleName());
            return;
        }

        ctor("Text", new PDAnnotationText());
        ctor("Link", new PDAnnotationLink());
        ctor("FreeText", new PDAnnotationFreeText());
        ctor("Line", new PDAnnotationLine());
        ctor("Square", new PDAnnotationSquare());
        ctor("Circle", new PDAnnotationCircle());
        ctor("Polygon", new PDAnnotationPolygon());
        ctor("PolyLine", new PDAnnotationPolyline());
        ctor("Highlight", new PDAnnotationHighlight());
        ctor("Underline", new PDAnnotationUnderline());
        ctor("Squiggly", new PDAnnotationSquiggly());
        ctor("StrikeOut", new PDAnnotationStrikeout());
        ctor("Stamp", new PDAnnotationRubberStamp());
        ctor("Caret", new PDAnnotationCaret());
        ctor("Ink", new PDAnnotationInk());
        ctor("Popup", new PDAnnotationPopup());
        ctor("FileAttachment", new PDAnnotationFileAttachment());
        ctor("Sound", new PDAnnotationSound());
        ctor("Widget", new PDAnnotationWidget());
    }
}
