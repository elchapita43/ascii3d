#!/usr/bin/env swift
import Carbon

// Obtener input sources disponibles
guard let inputSources = TISCreateInputSourceList(nil, false)?.takeRetainedValue() as? [TISInputSource] else {
    print("Error: No se pudieron obtener input sources")
    exit(1)
}

print("Buscando layout Español...")

for source in inputSources {
    guard let namePtr = TISGetInputSourceProperty(source, kTISPropertyLocalizedName) else { continue }
    let name = unsafeBitCast(namePtr, to: CFString.self) as String
    
    if name.contains("Spanish") || name.contains("Español") {
        print("Encontrado: \(name)")
        
        // Verificar si es layout (no input method)
        guard let typePtr = TISGetInputSourceProperty(source, kTISPropertyInputSourceType) else { continue }
        let type = unsafeBitCast(typePtr, to: CFString.self) as String
        
        if type == "TISTypeKeyboardLayout" {
            // Seleccionar este input source
            let status = TISSelectInputSource(source)
            if status == noErr {
                print("✅ Layout '\(name)' seleccionado exitosamente!")
                exit(0)
            } else {
                print("Error al seleccionar: \(status)")
            }
        }
    }
}

print("No se encontró layout Español")
print("Layouts disponibles:")
for source in inputSources {
    guard let namePtr = TISGetInputSourceProperty(source, kTISPropertyLocalizedName) else { continue }
    let name = unsafeBitCast(namePtr, to: CFString.self) as String
    print("  - \(name)")
}
