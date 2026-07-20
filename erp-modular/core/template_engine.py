"""Template Engine — Jinja2 + custom loader สำหรับ ERP Modular

ให้ Module ต่างๆ reuse template ร่วมกันผ่าน API
- โหลด template จาก Database (Template model) หรือ Filesystem
- render template ด้วย context ที่ส่งมา
- เก็บ rendered output กลับเข้า database (optional)
"""

import os
import json
from typing import Any, Optional
from jinja2 import Environment, BaseLoader, TemplateNotFound
from sqlmodel import Session, select


# ─── Custom Loader ────────────────────────────────────────────────────────

class DBTemplateLoader(BaseLoader):
    """Jinja2 loader ที่โหลด template content จาก Database"""

    def __init__(self, get_session_fn, template_type: Optional[str] = None):
        self.get_session = get_session_fn
        self.template_type = template_type

    def get_source(self, environment: Environment, template: str):
        """ค้นหา template จาก DB ด้วย slug หรือ name"""
        from models.entity import Template as TemplateModel

        session = self.get_session()
        try:
            # ลองค้นหาด้วย slug ก่อน
            stmt = select(TemplateModel).where(TemplateModel.slug == template)
            if self.template_type:
                stmt = stmt.where(TemplateModel.template_type == self.template_type)
            tmpl = session.exec(stmt).first()

            # ถ้าไม่เจอ ลองค้นหาด้วย name
            if not tmpl:
                stmt = select(TemplateModel).where(TemplateModel.name == template)
                if self.template_type:
                    stmt = stmt.where(TemplateModel.template_type == self.template_type)
                tmpl = session.exec(stmt).first()

            if not tmpl:
                raise TemplateNotFound(template)

            source = tmpl.schema_def.get("template_content", "")
            if not source:
                # fallback: ใช้ schema_def ทั้งหมดเป็น JSON string
                source = json.dumps(tmpl.schema_def, indent=2, ensure_ascii=False)

            return source, None, lambda: True
        finally:
            session.close()


class FileTemplateLoader(BaseLoader):
    """Jinja2 loader ที่โหลด template จาก filesystem"""

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = template_dir

    def get_source(self, environment: Environment, template: str):
        path = os.path.join(self.template_dir, template)
        if not os.path.isfile(path):
            raise TemplateNotFound(template)
        mtime = os.path.getmtime(path)
        with open(path, encoding="utf-8") as f:
            source = f.read()
        return source, path, lambda: mtime == os.path.getmtime(path)


# ─── Composite Loader ─────────────────────────────────────────────────────

class CompositeLoader(BaseLoader):
    """Jinja2 loader ที่ลอง loaders หลายตัวตามลำดับ"""

    def __init__(self, loaders: list[BaseLoader]):
        self.loaders = loaders

    def get_source(self, environment: Environment, template: str):
        errors = []
        for loader in self.loaders:
            try:
                return loader.get_source(environment, template)
            except TemplateNotFound as e:
                errors.append(str(e))
        raise TemplateNotFound(
            f"ไม่พบ template '{template}' ใน loaders ใดเลย: {', '.join(errors)}"
        )


# ─── Template Engine ──────────────────────────────────────────────────────

class TemplateEngine:
    """Engine หลักสำหรับ render template

    ใช้งาน:
        engine = TemplateEngine(get_session)
        html = engine.render("invoice-tmpl", {"customer": "สมชาย", "amount": 5000})
    """

    def __init__(self, get_session_fn, template_dirs: Optional[list[str]] = None):
        self.get_session = get_session_fn
        loaders = []

        # 1. DB loader (priority สูงสุด)
        loaders.append(DBTemplateLoader(get_session_fn))

        # 2. File loaders (fallback)
        if template_dirs:
            for d in template_dirs:
                loaders.append(FileTemplateLoader(d))
        else:
            loaders.append(FileTemplateLoader("templates"))

        # Jinja2 environment พร้อม composite loader
        self.env = Environment(
            loader=CompositeLoader(loaders),
            autoescape=True,
        )

        # ลงทะเบียน filters พื้นฐาน
        self.env.filters["json"] = lambda v: json.dumps(v, ensure_ascii=False, indent=2)
        self.env.filters["currency"] = lambda v, sym="฿": f"{sym}{v:,.2f}"

    def render(self, template_slug: str, context: dict[str, Any] = None) -> str:
        """Render template ด้วย context

        Args:
            template_slug: slug หรือ name ของ template
            context: ข้อมูลที่จะส่งเข้า template

        Returns:
            ข้อความที่ render แล้ว
        """
        if context is None:
            context = {}
        tmpl = self.env.get_template(template_slug)
        return tmpl.render(**context)

    def render_from_content(self, content: str, context: dict[str, Any] = None) -> str:
        """Render template จาก string โดยตรง (ไม่ได้บันทึกใน DB)"""
        if context is None:
            context = {}
        tmpl = self.env.from_string(content)
        return tmpl.render(**context)

    def register_template_content(
        self,
        session: Session,
        name: str,
        slug: str,
        content: str,
        template_type: str = "entity",
        module_id: Optional[int] = None,
        description: Optional[str] = None,
    ) -> Any:
        """บันทึก template content ลง database"""
        from models.entity import Template, TemplateCreate

        data = TemplateCreate(
            name=name,
            slug=slug,
            description=description or "",
            template_type=template_type,
            schema_def={"template_content": content},
            module_id=module_id,
        )
        db_tmpl = Template(**data.model_dump())
        session.add(db_tmpl)
        session.commit()
        session.refresh(db_tmpl)
        return db_tmpl
