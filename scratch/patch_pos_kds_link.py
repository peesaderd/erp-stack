with open('scratch/PosRestodash.vue', 'r', encoding='utf-8') as f:
    content = f.read()

target = '''          <div class="kds-header-controls">
            <button
              @click="toggleKdsSound"'''

replacement = '''          <div class="kds-header-controls">
            <!-- Open Standalone Screen in new window/tab -->
            <a
              href="/pos/kds"
              target="_blank"
              class="btn-open-standalone-kds"
              title="เปิดจอครัวเต็มจอในแท็บใหม่ หรือบนจอแท็บเล็ตแยก (Standalone KDS)"
            >
              <span>↗ จอครัวแยก (Standalone)</span>
            </a>
            <button
              @click="toggleKdsSound"'''

assert target in content, "target not found in PosRestodash.vue"
content = content.replace(target, replacement, 1)

css_target = '.kds-modal-box {'
css_replacement = '''.btn-open-standalone-kds {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: #2563EB;
  color: #ffffff !important;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-open-standalone-kds:hover {
  background: #1D4ED8;
  transform: translateY(-1px);
}
.kds-sound-toggle-btn {
  padding: 6px 12px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #059669;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.kds-sound-toggle-btn.is-muted {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.35);
  color: #DC2626;
}
.kds-test-sound-btn {
  padding: 6px 12px;
  background: #FFFBEB;
  border: 1px solid #FDE68A;
  color: #D97706;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.kds-modal-box {'''

assert css_target in content, "css_target not found in PosRestodash.vue"
content = content.replace(css_target, css_replacement, 1)

with open('scratch/PosRestodash.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print("PosRestodash.vue patched with Standalone KDS button and styling!")
