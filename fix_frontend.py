#!/usr/bin/env python3
"""Fix the frontend file with proper encoding."""

with open('frontend/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace lines 241-267 with new content
new_section = '''                <!-- 2) Medication Changes -->
                <div class="bg-white rounded-xl shadow-lg overflow-hidden fade-in border border-gray-100" style="animation-delay: 0.2s">
                    <div class="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-5 py-4">
                        <div class="flex items-center gap-3">
                            <span class="bg-white/20 rounded-lg px-3 py-1 text-lg font-bold">2</span>
                            <div>
                                <h3 class="font-bold">Medication Changes</h3>
                                <p class="text-purple-200 text-xs">START / STOP / CHANGE</p>
                            </div>
                        </div>
                    </div>
                    <div id="medications" class="p-5 text-gray-700 text-sm leading-relaxed min-h-[120px]"></div>
                </div>

                <!-- 3) Patient Education -->
                <div class="bg-white rounded-xl shadow-lg overflow-hidden fade-in border border-gray-100" style="animation-delay: 0.3s">
                    <div class="bg-gradient-to-r from-emerald-600 to-emerald-700 text-white px-5 py-4">
                        <div class="flex items-center gap-3">
                            <span class="bg-white/20 rounded-lg px-3 py-1 text-lg font-bold">3</span>
                            <div>
                                <h3 class="font-bold">Patient Education</h3>
                                <p class="text-emerald-200 text-xs">Lifestyle and counseling</p>
                            </div>
                        </div>
                    </div>
                    <div id="education" class="p-5 text-gray-700 text-sm leading-relaxed min-h-[120px]"></div>
                </div>

                <!-- 4) Monitoring -->
                <div class="bg-white rounded-xl shadow-lg overflow-hidden fade-in border border-gray-100" style="animation-delay: 0.4s">
                    <div class="bg-gradient-to-r from-orange-500 to-orange-600 text-white px-5 py-4">
                        <div class="flex items-center gap-3">
                            <span class="bg-white/20 rounded-lg px-3 py-1 text-lg font-bold">4</span>
                            <div>
                                <h3 class="font-bold">Monitoring and Next Steps</h3>
                                <p class="text-orange-200 text-xs">Tests, follow-ups, red flags</p>
                            </div>
                        </div>
                    </div>
                    <div id="monitoring" class="p-5 text-gray-700 text-sm leading-relaxed min-h-[120px]"></div>
                </div>
            </div>
'''

# Lines 240-266 (0-indexed: 240-266)
new_lines = lines[:240] + [new_section] + lines[267:]

with open('frontend/main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed frontend/main.py")

