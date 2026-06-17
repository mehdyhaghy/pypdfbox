import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.DefaultResourceCache;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;

/** Differential fuzz probe for recursive/deep PDResources graph lookup. */
public final class ResourcesRecursiveFuzzProbe {
    private static final COSName F1 = COSName.getPDFName("F1");
    private static final COSName F2 = COSName.getPDFName("F2");
    private static final COSName IM1 = COSName.getPDFName("Im1");
    private static final COSName CS1 = COSName.getPDFName("CS1");
    private static final COSName GS1 = COSName.getPDFName("GS1");
    private static final COSName RESOURCES = COSName.RESOURCES;
    private static final COSName PAGES = COSName.PAGES;
    private static final COSName PARENT = COSName.PARENT;
    private static final COSName TYPE = COSName.TYPE;

    interface Cell {
        String get() throws Throwable;
    }

    private static String safe(Cell cell) {
        try {
            return cell.get();
        } catch (Throwable error) {
            return "ERR:" + error.getClass().getSimpleName();
        }
    }

    private static String name(Object object) {
        return object == null ? "null" : object.getClass().getSimpleName();
    }

    private static COSDictionary fontDict() {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setItem(COSName.TYPE, COSName.FONT);
        dictionary.setName(COSName.SUBTYPE, "Type1");
        dictionary.setName(COSName.BASE_FONT, "Helvetica");
        return dictionary;
    }

    private static COSDictionary fontResources(Object value) {
        COSDictionary font = new COSDictionary();
        if (value instanceof org.apache.pdfbox.cos.COSBase) {
            font.setItem(F1, (org.apache.pdfbox.cos.COSBase) value);
        }
        COSDictionary resources = new COSDictionary();
        resources.setItem(COSName.FONT, font);
        return resources;
    }

    private static COSStream image(String colorSpaceName) {
        COSStream stream = new COSStream();
        stream.setName(COSName.SUBTYPE, "Image");
        stream.setInt(COSName.WIDTH, 1);
        stream.setInt(COSName.HEIGHT, 1);
        stream.setInt(COSName.BITS_PER_COMPONENT, 8);
        stream.setItem(COSName.COLORSPACE, COSName.getPDFName(colorSpaceName));
        return stream;
    }

    private static COSDictionary xobjectResources(COSObject imageRef, boolean namedColorSpace) {
        COSDictionary xobjects = new COSDictionary();
        xobjects.setItem(IM1, imageRef);
        COSDictionary resources = new COSDictionary();
        resources.setItem(COSName.XOBJECT, xobjects);
        if (namedColorSpace) {
            COSDictionary colorSpaces = new COSDictionary();
            colorSpaces.setItem(CS1, COSName.DEVICERGB);
            resources.setItem(COSName.COLORSPACE, colorSpaces);
        }
        return resources;
    }

    private static COSDictionary colorSpaceResources(Object value) {
        COSDictionary colorSpaces = new COSDictionary();
        if (value instanceof org.apache.pdfbox.cos.COSBase) {
            colorSpaces.setItem(CS1, (org.apache.pdfbox.cos.COSBase) value);
        }
        COSDictionary resources = new COSDictionary();
        resources.setItem(COSName.COLORSPACE, colorSpaces);
        return resources;
    }

    private static COSDictionary extStateResources(Object value) {
        COSDictionary extStates = new COSDictionary();
        if (value instanceof org.apache.pdfbox.cos.COSBase) {
            extStates.setItem(GS1, (org.apache.pdfbox.cos.COSBase) value);
        }
        COSDictionary resources = new COSDictionary();
        resources.setItem(COSName.EXT_G_STATE, extStates);
        return resources;
    }

    private static COSDictionary extStateDict() {
        COSDictionary dictionary = new COSDictionary();
        dictionary.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        dictionary.setFloat(COSName.getPDFName("ca"), 0.5f);
        return dictionary;
    }

    private static String fontTwice(PDResources resources, COSName name) {
        return safe(() -> {
            PDFont first = resources.getFont(name);
            PDFont second = resources.getFont(name);
            return name(first) + "/" + (first == second ? "1" : "0");
        });
    }

    private static String fontAlias(PDResources resources) {
        return safe(() -> {
            PDFont first = resources.getFont(F1);
            PDFont second = resources.getFont(F2);
            return name(first) + "," + name(second) + "/" + (first == second ? "1" : "0");
        });
    }

    private static String colorSpaceTwice(PDResources resources) {
        return safe(() -> {
            PDColorSpace first = resources.getColorSpace(CS1);
            PDColorSpace second = resources.getColorSpace(CS1);
            return name(first) + "/" + (first == second ? "1" : "0");
        });
    }

    private static String xobjectTwice(PDResources resources) {
        return safe(() -> {
            PDXObject first = resources.getXObject(IM1);
            PDXObject second = resources.getXObject(IM1);
            return name(first) + "/" + (first == second ? "1" : "0");
        });
    }

    private static String extStateTwice(PDResources resources) {
        return safe(() -> {
            PDExtendedGraphicsState first = resources.getExtGState(GS1);
            PDExtendedGraphicsState second = resources.getExtGState(GS1);
            return name(first) + "/" + (first == second ? "1" : "0");
        });
    }

    private static String malformedCell(PDResources resources) {
        return "f=" + safe(() -> name(resources.getFont(F1)))
                + " x=" + safe(() -> name(resources.getXObject(IM1)))
                + " c=" + safe(() -> name(resources.getColorSpace(CS1)))
                + " p=" + safe(() -> name(resources.getPattern(COSName.getPDFName("P1"))))
                + " g=" + safe(() -> name(resources.getExtGState(GS1)));
    }

    private static String pageFont(PDPage page) {
        return safe(() -> {
            PDResources firstResources = page.getResources();
            PDResources secondResources = page.getResources();
            if (firstResources == null || secondResources == null) {
                return "res=null";
            }
            PDFont firstFont = firstResources.getFont(F1);
            PDFont secondFont = secondResources.getFont(F1);
            return "res=PDResources/" + (firstResources == secondResources ? "1" : "0")
                    + " font=" + name(firstFont) + "/" + (firstFont == secondFont ? "1" : "0");
        });
    }

    private static PDPage pageWithParents(COSDictionary pageDict, int depth, COSDictionary resources) {
        COSDictionary child = pageDict;
        for (int i = 0; i < depth; i++) {
            COSDictionary parent = new COSDictionary();
            parent.setItem(TYPE, PAGES);
            child.setItem(PARENT, parent);
            child = parent;
        }
        child.setItem(RESOURCES, resources);
        return new PDPage(pageDict);
    }

    private static void emit(PrintStream out, String id, String value) {
        out.println("CASE " + id + " " + value);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        COSDictionary directFont = fontDict();
        emit(out, "fdir", fontTwice(new PDResources(fontResources(directFont)), F1));

        COSObject indirectFont = new COSObject(fontDict());
        emit(out, "find", fontTwice(new PDResources(fontResources(indirectFont),
                new DefaultResourceCache()), F1));

        COSDictionary aliasDirect = new COSDictionary();
        COSDictionary aliasDirectFont = new COSDictionary();
        aliasDirectFont.setItem(F1, directFont);
        aliasDirectFont.setItem(F2, directFont);
        aliasDirect.setItem(COSName.FONT, aliasDirectFont);
        emit(out, "fali", fontAlias(new PDResources(aliasDirect)));

        COSDictionary aliasIndirect = new COSDictionary();
        COSDictionary aliasIndirectFont = new COSDictionary();
        COSObject sharedIndirectFont = new COSObject(fontDict());
        aliasIndirectFont.setItem(F1, sharedIndirectFont);
        aliasIndirectFont.setItem(F2, sharedIndirectFont);
        aliasIndirect.setItem(COSName.FONT, aliasIndirectFont);
        emit(out, "fain", fontAlias(new PDResources(aliasIndirect, new DefaultResourceCache())));

        COSDictionary indirectCategory = new COSDictionary();
        indirectCategory.setItem(COSName.FONT, new COSObject(fontResources(fontDict()).getDictionaryObject(COSName.FONT)));
        emit(out, "cind", fontTwice(new PDResources(indirectCategory), F1));

        COSDictionary chainedCategory = new COSDictionary();
        chainedCategory.setItem(COSName.FONT,
                new COSObject(new COSObject(fontResources(fontDict()).getDictionaryObject(COSName.FONT))));
        emit(out, "cchn", fontTwice(new PDResources(chainedCategory), F1));

        emit(out, "fnul", fontTwice(new PDResources(fontResources(new COSObject(null))), F1));
        emit(out, "fchn", fontTwice(new PDResources(fontResources(new COSObject(new COSObject(fontDict())))), F1));

        COSObject cachedImage = new COSObject(image("DeviceGray"));
        emit(out, "xyes", xobjectTwice(new PDResources(xobjectResources(cachedImage, false),
                new DefaultResourceCache())));

        COSObject uncachedImage = new COSObject(image("CS1"));
        emit(out, "xnoc", xobjectTwice(new PDResources(xobjectResources(uncachedImage, true),
                new DefaultResourceCache())));

        emit(out, "cpat", colorSpaceTwice(new PDResources(
                colorSpaceResources(new COSObject(COSName.PATTERN)), new DefaultResourceCache())));

        COSDictionary nullColorSpaces = new COSDictionary();
        nullColorSpaces.setItem(CS1, COSNull.NULL);
        COSDictionary nullResources = new COSDictionary();
        nullResources.setItem(COSName.COLORSPACE, nullColorSpaces);
        PDResources nullColorResource = new PDResources(nullResources);
        emit(out, "cnull", "has=" + (nullColorResource.hasColorSpace(CS1) ? "1" : "0")
                + " get=" + colorSpaceTwice(nullColorResource));

        emit(out, "gsin", extStateTwice(new PDResources(
                extStateResources(new COSObject(extStateDict())), new DefaultResourceCache())));

        COSDictionary malformed = new COSDictionary();
        COSDictionary malformedFonts = new COSDictionary();
        malformedFonts.setItem(F1, new COSObject(new COSArray()));
        malformed.setItem(COSName.FONT, malformedFonts);
        COSDictionary malformedXObjects = new COSDictionary();
        malformedXObjects.setItem(IM1, new COSObject(COSInteger.ONE));
        malformed.setItem(COSName.XOBJECT, malformedXObjects);
        COSDictionary malformedColorSpaces = new COSDictionary();
        malformedColorSpaces.setItem(CS1, new COSObject(COSName.getPDFName("UnknownCS")));
        malformed.setItem(COSName.COLORSPACE, malformedColorSpaces);
        COSDictionary malformedPatterns = new COSDictionary();
        malformedPatterns.setItem(COSName.getPDFName("P1"), new COSObject(COSInteger.ONE));
        malformed.setItem(COSName.PATTERN, malformedPatterns);
        COSDictionary malformedExtStates = new COSDictionary();
        malformedExtStates.setItem(GS1, new COSObject(new COSArray()));
        malformed.setItem(COSName.EXT_G_STATE, malformedExtStates);
        emit(out, "mbad", malformedCell(new PDResources(malformed,
                new DefaultResourceCache())));

        COSDictionary nested = new COSDictionary();
        nested.setItem(RESOURCES, fontResources(fontDict()));
        emit(out, "nest", fontTwice(new PDResources(nested), F1));

        COSDictionary selfNested = new COSDictionary();
        selfNested.setItem(RESOURCES, selfNested);
        emit(out, "self", fontTwice(new PDResources(selfNested), F1));

        COSDictionary wrongSubdict = new COSDictionary();
        wrongSubdict.setItem(COSName.FONT, new COSArray());
        PDResources createOverWrong = new PDResources(wrongSubdict);
        COSName created = createOverWrong.add(
                new PDType1Font(Standard14Fonts.FontName.HELVETICA));
        emit(out, "crbd", created.getName() + " " + fontTwice(createOverWrong, created));

        emit(out, "inhd", pageFont(pageWithParents(new COSDictionary(), 64, fontResources(fontDict()))));

        COSDictionary localEmpty = new COSDictionary();
        localEmpty.setItem(RESOURCES, new COSDictionary());
        emit(out, "inhe", pageFont(pageWithParents(localEmpty, 2, fontResources(fontDict()))));

        COSDictionary localNull = new COSDictionary();
        localNull.setItem(RESOURCES, COSNull.NULL);
        emit(out, "inhn", pageFont(pageWithParents(localNull, 2, fontResources(fontDict()))));

        COSDictionary localWrong = new COSDictionary();
        localWrong.setItem(RESOURCES, COSInteger.ONE);
        emit(out, "inhw", pageFont(pageWithParents(localWrong, 2, fontResources(fontDict()))));

        COSDictionary pageStop = new COSDictionary();
        COSDictionary nonPagesParent = new COSDictionary();
        nonPagesParent.setItem(RESOURCES, fontResources(fontDict()));
        pageStop.setItem(PARENT, nonPagesParent);
        emit(out, "inhs", pageFont(new PDPage(pageStop)));

        COSDictionary pageCycle = new COSDictionary();
        COSDictionary parentA = new COSDictionary();
        COSDictionary parentB = new COSDictionary();
        parentA.setItem(TYPE, PAGES);
        parentB.setItem(TYPE, PAGES);
        pageCycle.setItem(PARENT, parentA);
        parentA.setItem(PARENT, parentB);
        parentB.setItem(PARENT, parentA);
        emit(out, "inhc", pageFont(new PDPage(pageCycle)));

        COSDictionary pageCycleHit = new COSDictionary();
        COSDictionary hitA = new COSDictionary();
        COSDictionary hitB = new COSDictionary();
        hitA.setItem(TYPE, PAGES);
        hitB.setItem(TYPE, PAGES);
        pageCycleHit.setItem(PARENT, hitA);
        hitA.setItem(PARENT, hitB);
        hitB.setItem(PARENT, hitA);
        hitB.setItem(RESOURCES, fontResources(fontDict()));
        emit(out, "inhh", pageFont(new PDPage(pageCycleHit)));
    }
}
