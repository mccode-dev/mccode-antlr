/*
 * This file was auto-generated by speedy-antlr-tool v1.4.3
 *  https://github.com/amykyta3/speedy-antlr-tool
 */

#include "sa_mccomp_translator.h"


SA_McCompTranslator::SA_McCompTranslator(speedy_antlr::Translator *translator) {
    this->translator = translator;
}

SA_McCompTranslator::~SA_McCompTranslator() {
    Py_XDECREF(ProgContext_cls);
    Py_XDECREF(ComponentDefineNewContext_cls);
    Py_XDECREF(ComponentDefineCopyContext_cls);
    Py_XDECREF(TraceBlockContext_cls);
    Py_XDECREF(TraceBlockCopyContext_cls);
    Py_XDECREF(Component_parameter_setContext_cls);
    Py_XDECREF(Component_define_parametersContext_cls);
    Py_XDECREF(Component_set_parametersContext_cls);
    Py_XDECREF(Component_out_parametersContext_cls);
    Py_XDECREF(Component_parametersContext_cls);
    Py_XDECREF(ComponentParameterSymbolContext_cls);
    Py_XDECREF(ComponentParameterDoubleArrayContext_cls);
    Py_XDECREF(ComponentParameterDoubleContext_cls);
    Py_XDECREF(ComponentParameterVectorContext_cls);
    Py_XDECREF(ComponentParameterIntegerContext_cls);
    Py_XDECREF(ComponentParameterIntegerArrayContext_cls);
    Py_XDECREF(ComponentParameterStringContext_cls);
    Py_XDECREF(ShareBlockContext_cls);
    Py_XDECREF(ShareBlockCopyContext_cls);
    Py_XDECREF(DisplayBlockCopyContext_cls);
    Py_XDECREF(DisplayBlockContext_cls);
    Py_XDECREF(Component_refContext_cls);
    Py_XDECREF(CoordsContext_cls);
    Py_XDECREF(ReferenceContext_cls);
    Py_XDECREF(DependencyContext_cls);
    Py_XDECREF(DeclareBlockContext_cls);
    Py_XDECREF(DeclareBlockCopyContext_cls);
    Py_XDECREF(UservarsContext_cls);
    Py_XDECREF(InitializeBlockContext_cls);
    Py_XDECREF(InitializeBlockCopyContext_cls);
    Py_XDECREF(SaveBlockCopyContext_cls);
    Py_XDECREF(SaveBlockContext_cls);
    Py_XDECREF(FinallyBlockContext_cls);
    Py_XDECREF(FinallyBlockCopyContext_cls);
    Py_XDECREF(MetadataContext_cls);
    Py_XDECREF(CategoryContext_cls);
    Py_XDECREF(InitializerlistContext_cls);
    Py_XDECREF(AssignmentContext_cls);
    Py_XDECREF(ExpressionBinaryModContext_cls);
    Py_XDECREF(ExpressionBinaryLessContext_cls);
    Py_XDECREF(ExpressionBinaryGreaterContext_cls);
    Py_XDECREF(ExpressionBinaryLessEqualContext_cls);
    Py_XDECREF(ExpressionArrayAccessContext_cls);
    Py_XDECREF(ExpressionBinaryLogicContext_cls);
    Py_XDECREF(ExpressionIntegerContext_cls);
    Py_XDECREF(ExpressionBinaryRightShiftContext_cls);
    Py_XDECREF(ExpressionMyselfContext_cls);
    Py_XDECREF(ExpressionPreviousContext_cls);
    Py_XDECREF(ExpressionIdentifierContext_cls);
    Py_XDECREF(ExpressionStructAccessContext_cls);
    Py_XDECREF(ExpressionFunctionCallContext_cls);
    Py_XDECREF(ExpressionBinaryMDContext_cls);
    Py_XDECREF(ExpressionStringContext_cls);
    Py_XDECREF(ExpressionGroupingContext_cls);
    Py_XDECREF(ExpressionExponentiationContext_cls);
    Py_XDECREF(ExpressionBinaryLeftShiftContext_cls);
    Py_XDECREF(ExpressionBinaryGreaterEqualContext_cls);
    Py_XDECREF(ExpressionZeroContext_cls);
    Py_XDECREF(ExpressionUnaryPMContext_cls);
    Py_XDECREF(ExpressionTrinaryLogicContext_cls);
    Py_XDECREF(ExpressionFloatContext_cls);
    Py_XDECREF(ExpressionPointerAccessContext_cls);
    Py_XDECREF(ExpressionBinaryEqualContext_cls);
    Py_XDECREF(ExpressionBinaryPMContext_cls);
    Py_XDECREF(ExpressionUnaryLogicContext_cls);
    Py_XDECREF(ShellContext_cls);
    Py_XDECREF(SearchPathContext_cls);
    Py_XDECREF(SearchShellContext_cls);
    Py_XDECREF(Unparsed_blockContext_cls);
}


antlrcpp::Any SA_McCompTranslator::visitProg(McCompParser::ProgContext *ctx){
    if(!ProgContext_cls) ProgContext_cls = PyObject_GetAttrString(translator->parser_cls, "ProgContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ProgContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentDefineNew(McCompParser::ComponentDefineNewContext *ctx){
    if(!ComponentDefineNewContext_cls) ComponentDefineNewContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentDefineNewContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentDefineNewContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentDefineCopy(McCompParser::ComponentDefineCopyContext *ctx){
    if(!ComponentDefineCopyContext_cls) ComponentDefineCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentDefineCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentDefineCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitTraceBlock(McCompParser::TraceBlockContext *ctx){
    if(!TraceBlockContext_cls) TraceBlockContext_cls = PyObject_GetAttrString(translator->parser_cls, "TraceBlockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, TraceBlockContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitTraceBlockCopy(McCompParser::TraceBlockCopyContext *ctx){
    if(!TraceBlockCopyContext_cls) TraceBlockCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "TraceBlockCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, TraceBlockCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponent_parameter_set(McCompParser::Component_parameter_setContext *ctx){
    if(!Component_parameter_setContext_cls) Component_parameter_setContext_cls = PyObject_GetAttrString(translator->parser_cls, "Component_parameter_setContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, Component_parameter_setContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponent_define_parameters(McCompParser::Component_define_parametersContext *ctx){
    if(!Component_define_parametersContext_cls) Component_define_parametersContext_cls = PyObject_GetAttrString(translator->parser_cls, "Component_define_parametersContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, Component_define_parametersContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponent_set_parameters(McCompParser::Component_set_parametersContext *ctx){
    if(!Component_set_parametersContext_cls) Component_set_parametersContext_cls = PyObject_GetAttrString(translator->parser_cls, "Component_set_parametersContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, Component_set_parametersContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponent_out_parameters(McCompParser::Component_out_parametersContext *ctx){
    if(!Component_out_parametersContext_cls) Component_out_parametersContext_cls = PyObject_GetAttrString(translator->parser_cls, "Component_out_parametersContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, Component_out_parametersContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponent_parameters(McCompParser::Component_parametersContext *ctx){
    if(!Component_parametersContext_cls) Component_parametersContext_cls = PyObject_GetAttrString(translator->parser_cls, "Component_parametersContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, Component_parametersContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentParameterSymbol(McCompParser::ComponentParameterSymbolContext *ctx){
    if(!ComponentParameterSymbolContext_cls) ComponentParameterSymbolContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentParameterSymbolContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentParameterSymbolContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentParameterDoubleArray(McCompParser::ComponentParameterDoubleArrayContext *ctx){
    if(!ComponentParameterDoubleArrayContext_cls) ComponentParameterDoubleArrayContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentParameterDoubleArrayContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentParameterDoubleArrayContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentParameterDouble(McCompParser::ComponentParameterDoubleContext *ctx){
    if(!ComponentParameterDoubleContext_cls) ComponentParameterDoubleContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentParameterDoubleContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentParameterDoubleContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentParameterVector(McCompParser::ComponentParameterVectorContext *ctx){
    if(!ComponentParameterVectorContext_cls) ComponentParameterVectorContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentParameterVectorContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentParameterVectorContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentParameterInteger(McCompParser::ComponentParameterIntegerContext *ctx){
    if(!ComponentParameterIntegerContext_cls) ComponentParameterIntegerContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentParameterIntegerContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentParameterIntegerContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentParameterIntegerArray(McCompParser::ComponentParameterIntegerArrayContext *ctx){
    if(!ComponentParameterIntegerArrayContext_cls) ComponentParameterIntegerArrayContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentParameterIntegerArrayContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentParameterIntegerArrayContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponentParameterString(McCompParser::ComponentParameterStringContext *ctx){
    if(!ComponentParameterStringContext_cls) ComponentParameterStringContext_cls = PyObject_GetAttrString(translator->parser_cls, "ComponentParameterStringContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ComponentParameterStringContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitShareBlock(McCompParser::ShareBlockContext *ctx){
    if(!ShareBlockContext_cls) ShareBlockContext_cls = PyObject_GetAttrString(translator->parser_cls, "ShareBlockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ShareBlockContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitShareBlockCopy(McCompParser::ShareBlockCopyContext *ctx){
    if(!ShareBlockCopyContext_cls) ShareBlockCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "ShareBlockCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ShareBlockCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitDisplayBlockCopy(McCompParser::DisplayBlockCopyContext *ctx){
    if(!DisplayBlockCopyContext_cls) DisplayBlockCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "DisplayBlockCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, DisplayBlockCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitDisplayBlock(McCompParser::DisplayBlockContext *ctx){
    if(!DisplayBlockContext_cls) DisplayBlockContext_cls = PyObject_GetAttrString(translator->parser_cls, "DisplayBlockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, DisplayBlockContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitComponent_ref(McCompParser::Component_refContext *ctx){
    if(!Component_refContext_cls) Component_refContext_cls = PyObject_GetAttrString(translator->parser_cls, "Component_refContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, Component_refContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitCoords(McCompParser::CoordsContext *ctx){
    if(!CoordsContext_cls) CoordsContext_cls = PyObject_GetAttrString(translator->parser_cls, "CoordsContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, CoordsContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitReference(McCompParser::ReferenceContext *ctx){
    if(!ReferenceContext_cls) ReferenceContext_cls = PyObject_GetAttrString(translator->parser_cls, "ReferenceContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ReferenceContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitDependency(McCompParser::DependencyContext *ctx){
    if(!DependencyContext_cls) DependencyContext_cls = PyObject_GetAttrString(translator->parser_cls, "DependencyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, DependencyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitDeclareBlock(McCompParser::DeclareBlockContext *ctx){
    if(!DeclareBlockContext_cls) DeclareBlockContext_cls = PyObject_GetAttrString(translator->parser_cls, "DeclareBlockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, DeclareBlockContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitDeclareBlockCopy(McCompParser::DeclareBlockCopyContext *ctx){
    if(!DeclareBlockCopyContext_cls) DeclareBlockCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "DeclareBlockCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, DeclareBlockCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitUservars(McCompParser::UservarsContext *ctx){
    if(!UservarsContext_cls) UservarsContext_cls = PyObject_GetAttrString(translator->parser_cls, "UservarsContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, UservarsContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitInitializeBlock(McCompParser::InitializeBlockContext *ctx){
    if(!InitializeBlockContext_cls) InitializeBlockContext_cls = PyObject_GetAttrString(translator->parser_cls, "InitializeBlockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, InitializeBlockContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitInitializeBlockCopy(McCompParser::InitializeBlockCopyContext *ctx){
    if(!InitializeBlockCopyContext_cls) InitializeBlockCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "InitializeBlockCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, InitializeBlockCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitSaveBlockCopy(McCompParser::SaveBlockCopyContext *ctx){
    if(!SaveBlockCopyContext_cls) SaveBlockCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "SaveBlockCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, SaveBlockCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitSaveBlock(McCompParser::SaveBlockContext *ctx){
    if(!SaveBlockContext_cls) SaveBlockContext_cls = PyObject_GetAttrString(translator->parser_cls, "SaveBlockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, SaveBlockContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitFinallyBlock(McCompParser::FinallyBlockContext *ctx){
    if(!FinallyBlockContext_cls) FinallyBlockContext_cls = PyObject_GetAttrString(translator->parser_cls, "FinallyBlockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, FinallyBlockContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitFinallyBlockCopy(McCompParser::FinallyBlockCopyContext *ctx){
    if(!FinallyBlockCopyContext_cls) FinallyBlockCopyContext_cls = PyObject_GetAttrString(translator->parser_cls, "FinallyBlockCopyContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, FinallyBlockCopyContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitMetadata(McCompParser::MetadataContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"mime", static_cast<void*>(ctx->mime)},
        {"name", static_cast<void*>(ctx->name)}
    };
    if(!MetadataContext_cls) MetadataContext_cls = PyObject_GetAttrString(translator->parser_cls, "MetadataContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, MetadataContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitCategory(McCompParser::CategoryContext *ctx){
    if(!CategoryContext_cls) CategoryContext_cls = PyObject_GetAttrString(translator->parser_cls, "CategoryContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, CategoryContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitInitializerlist(McCompParser::InitializerlistContext *ctx){
    if(!InitializerlistContext_cls) InitializerlistContext_cls = PyObject_GetAttrString(translator->parser_cls, "InitializerlistContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, InitializerlistContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitAssignment(McCompParser::AssignmentContext *ctx){
    if(!AssignmentContext_cls) AssignmentContext_cls = PyObject_GetAttrString(translator->parser_cls, "AssignmentContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, AssignmentContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryMod(McCompParser::ExpressionBinaryModContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryModContext_cls) ExpressionBinaryModContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryModContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryModContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryLess(McCompParser::ExpressionBinaryLessContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryLessContext_cls) ExpressionBinaryLessContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryLessContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryLessContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryGreater(McCompParser::ExpressionBinaryGreaterContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryGreaterContext_cls) ExpressionBinaryGreaterContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryGreaterContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryGreaterContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryLessEqual(McCompParser::ExpressionBinaryLessEqualContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryLessEqualContext_cls) ExpressionBinaryLessEqualContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryLessEqualContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryLessEqualContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionArrayAccess(McCompParser::ExpressionArrayAccessContext *ctx){
    if(!ExpressionArrayAccessContext_cls) ExpressionArrayAccessContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionArrayAccessContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionArrayAccessContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryLogic(McCompParser::ExpressionBinaryLogicContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryLogicContext_cls) ExpressionBinaryLogicContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryLogicContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryLogicContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionInteger(McCompParser::ExpressionIntegerContext *ctx){
    if(!ExpressionIntegerContext_cls) ExpressionIntegerContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionIntegerContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionIntegerContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryRightShift(McCompParser::ExpressionBinaryRightShiftContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryRightShiftContext_cls) ExpressionBinaryRightShiftContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryRightShiftContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryRightShiftContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionMyself(McCompParser::ExpressionMyselfContext *ctx){
    if(!ExpressionMyselfContext_cls) ExpressionMyselfContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionMyselfContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionMyselfContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionPrevious(McCompParser::ExpressionPreviousContext *ctx){
    if(!ExpressionPreviousContext_cls) ExpressionPreviousContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionPreviousContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionPreviousContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionIdentifier(McCompParser::ExpressionIdentifierContext *ctx){
    if(!ExpressionIdentifierContext_cls) ExpressionIdentifierContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionIdentifierContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionIdentifierContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionStructAccess(McCompParser::ExpressionStructAccessContext *ctx){
    if(!ExpressionStructAccessContext_cls) ExpressionStructAccessContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionStructAccessContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionStructAccessContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionFunctionCall(McCompParser::ExpressionFunctionCallContext *ctx){
    if(!ExpressionFunctionCallContext_cls) ExpressionFunctionCallContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionFunctionCallContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionFunctionCallContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryMD(McCompParser::ExpressionBinaryMDContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryMDContext_cls) ExpressionBinaryMDContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryMDContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryMDContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionString(McCompParser::ExpressionStringContext *ctx){
    if(!ExpressionStringContext_cls) ExpressionStringContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionStringContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionStringContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionGrouping(McCompParser::ExpressionGroupingContext *ctx){
    if(!ExpressionGroupingContext_cls) ExpressionGroupingContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionGroupingContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionGroupingContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionExponentiation(McCompParser::ExpressionExponentiationContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"base", static_cast<void*>(ctx->base)},
        {"exponent", static_cast<void*>(ctx->exponent)}
    };
    if(!ExpressionExponentiationContext_cls) ExpressionExponentiationContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionExponentiationContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionExponentiationContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryLeftShift(McCompParser::ExpressionBinaryLeftShiftContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryLeftShiftContext_cls) ExpressionBinaryLeftShiftContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryLeftShiftContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryLeftShiftContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryGreaterEqual(McCompParser::ExpressionBinaryGreaterEqualContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryGreaterEqualContext_cls) ExpressionBinaryGreaterEqualContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryGreaterEqualContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryGreaterEqualContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionZero(McCompParser::ExpressionZeroContext *ctx){
    if(!ExpressionZeroContext_cls) ExpressionZeroContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionZeroContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionZeroContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionUnaryPM(McCompParser::ExpressionUnaryPMContext *ctx){
    if(!ExpressionUnaryPMContext_cls) ExpressionUnaryPMContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionUnaryPMContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionUnaryPMContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionTrinaryLogic(McCompParser::ExpressionTrinaryLogicContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"test", static_cast<void*>(ctx->test)},
        {"true", static_cast<void*>(ctx->true)},
        {"false", static_cast<void*>(ctx->false)}
    };
    if(!ExpressionTrinaryLogicContext_cls) ExpressionTrinaryLogicContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionTrinaryLogicContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionTrinaryLogicContext_cls, labels, 3);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionFloat(McCompParser::ExpressionFloatContext *ctx){
    if(!ExpressionFloatContext_cls) ExpressionFloatContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionFloatContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionFloatContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionPointerAccess(McCompParser::ExpressionPointerAccessContext *ctx){
    if(!ExpressionPointerAccessContext_cls) ExpressionPointerAccessContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionPointerAccessContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionPointerAccessContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryEqual(McCompParser::ExpressionBinaryEqualContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryEqualContext_cls) ExpressionBinaryEqualContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryEqualContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryEqualContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionBinaryPM(McCompParser::ExpressionBinaryPMContext *ctx){
    speedy_antlr::LabelMap labels[] = {
        {"left", static_cast<void*>(ctx->left)},
        {"right", static_cast<void*>(ctx->right)}
    };
    if(!ExpressionBinaryPMContext_cls) ExpressionBinaryPMContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionBinaryPMContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionBinaryPMContext_cls, labels, 2);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitExpressionUnaryLogic(McCompParser::ExpressionUnaryLogicContext *ctx){
    if(!ExpressionUnaryLogicContext_cls) ExpressionUnaryLogicContext_cls = PyObject_GetAttrString(translator->parser_cls, "ExpressionUnaryLogicContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ExpressionUnaryLogicContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitShell(McCompParser::ShellContext *ctx){
    if(!ShellContext_cls) ShellContext_cls = PyObject_GetAttrString(translator->parser_cls, "ShellContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, ShellContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitSearchPath(McCompParser::SearchPathContext *ctx){
    if(!SearchPathContext_cls) SearchPathContext_cls = PyObject_GetAttrString(translator->parser_cls, "SearchPathContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, SearchPathContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitSearchShell(McCompParser::SearchShellContext *ctx){
    if(!SearchShellContext_cls) SearchShellContext_cls = PyObject_GetAttrString(translator->parser_cls, "SearchShellContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, SearchShellContext_cls);
    return py_ctx;
}

antlrcpp::Any SA_McCompTranslator::visitUnparsed_block(McCompParser::Unparsed_blockContext *ctx){
    if(!Unparsed_blockContext_cls) Unparsed_blockContext_cls = PyObject_GetAttrString(translator->parser_cls, "Unparsed_blockContext");
    PyObject *py_ctx = translator->convert_ctx(this, ctx, Unparsed_blockContext_cls);
    return py_ctx;
}
