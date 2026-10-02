$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json

function Result($ok, $reason, $items = @()) {
    @{ ok = $ok; reason = $reason; items = @($items) } | ConvertTo-Json -Compress -Depth 5
}

function Matches($element, $name, $id) {
    return ((-not $name -or $element.Current.Name -eq $name) -and
            (-not $id -or $element.Current.AutomationId -eq $id))
}

function QueryMatches($element, $query) {
    $needle = [string]$query
    if (-not $needle) { return $false }
    $name = [string]$element.Current.Name
    $id = [string]$element.Current.AutomationId
    return (($name -and $name.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) -or
            ($id -and $id.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0))
}

try {
    $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$request.hwnd)
    if ($null -eq $root) { Result $false 'window_missing'; exit 0 }
    $pidTarget = $root.Current.ProcessId
    $nodes = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants,
                           [System.Windows.Automation.Condition]::TrueCondition)
    $visible = @($nodes | Where-Object { -not $_.Current.IsOffscreen -and $_.Current.IsEnabled })
    if ($request.operation -eq 'inspect') {
        $items = @($visible | Where-Object { $_.Current.Name -or $_.Current.AutomationId } |
            Select-Object -First 160 | ForEach-Object {
                @{ name = $_.Current.Name; id = $_.Current.AutomationId;
                   role = $_.Current.ControlType.ProgrammaticName; focusable = $_.Current.IsKeyboardFocusable }
            })
        Result $true 'inspected' $items
        exit 0
    }
    if ($request.operation -eq 'project') {
        if (-not $request.name -and -not $request.id) { Result $false 'project_selector_missing'; exit 0 }
        $found = @($visible | Where-Object { Matches $_ $request.name $request.id })
        # Text labels may sit inside a clickable tree/list/button element.
        $actionable = @{}
        $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
        foreach ($node in $found) {
            for ($depth = 0; $depth -lt 4 -and $null -ne $node; $depth++) {
                if ($node.Current.ProcessId -ne $pidTarget -or $node.Equals($root)) { break }
                $pattern = $null
                $kind = ''
                if ($node.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) {
                    $kind = 'select'
                } elseif ($node.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
                    $kind = 'invoke'
                }
                if ($kind) {
                    $actionable[($node.GetRuntimeId() -join '.')] = @{ kind = $kind; pattern = $pattern }
                    break
                }
                $node = $walker.GetParent($node)
            }
        }
        if ($actionable.Count -ne 1) { Result $false 'project_missing_or_ambiguous' @(@{ matches = $found.Count; actions = $actionable.Count }); exit 0 }
        $action = @($actionable.Values)[0]
        if ($action.kind -eq 'select') { $action.pattern.Select() } else { $action.pattern.Invoke() }
        Result $true 'project_selected'
        exit 0
    }
    if ($request.operation -eq 'find_focus') {
        $query = [string]$request.query
        $found = @($visible | Where-Object { QueryMatches $_ $query })
        if ($found.Count -eq 0) { Result $false 'dialog_not_found'; exit 0 }

        # Prefer an exact task/dialog name over message text containing the
        # same word. Then resolve the clickable parent through UI Automation.
        $exact = @($found | Where-Object { $_.Current.Name -eq $query })
        if ($exact.Count -gt 0) { $found = $exact }
        $actionable = @{}
        $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
        foreach ($node in $found) {
            for ($depth = 0; $depth -lt 5 -and $null -ne $node; $depth++) {
                if ($node.Current.ProcessId -ne $pidTarget -or $node.Equals($root)) { break }
                $pattern = $null
                $kind = ''
                if ($node.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) {
                    $kind = 'select'
                } elseif ($node.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
                    $kind = 'invoke'
                }
                if ($kind) {
                    $actionable[($node.GetRuntimeId() -join '.')] = @{ kind = $kind; pattern = $pattern; name = $node.Current.Name }
                    break
                }
                $node = $walker.GetParent($node)
            }
        }
        if ($actionable.Count -ne 1) {
            $items = @($actionable.Values | ForEach-Object { @{ name = $_.name } })
            Result $false $(if ($actionable.Count -eq 0) { 'dialog_not_actionable' } else { 'dialog_ambiguous' }) $items
            exit 0
        }
        $action = @($actionable.Values)[0]
        if ($action.kind -eq 'select') { $action.pattern.Select() } else { $action.pattern.Invoke() }
        Result $true 'dialog_selected'
        exit 0
    }
    $edits = @($visible | Where-Object {
        $pattern = $null
        $editable = $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit
        if ($_.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
            $editable = -not $pattern.Current.IsReadOnly
        }
        $nonChat = (-not $request.name -and -not $request.id -and
            ($_.Current.Name + ' ' + $_.Current.AutomationId) -match '(?i)search|filter|address|\u641c\u7d22|\u67e5\u627e|\u7b5b\u9009|\u5730\u5740')
        $editable -and -not $nonChat -and $_.Current.IsKeyboardFocusable -and -not $_.Current.IsPassword -and
            (Matches $_ $request.name $request.id)
    })
    $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
    if ($request.operation -eq 'bind_project') {
        if ($null -eq $focused -or $focused.Current.ProcessId -ne $pidTarget) {
            Result $false 'task_not_focused'
            exit 0
        }
        $name = $focused.Current.Name
        $id = $focused.Current.AutomationId
        if (-not $name -and -not $id) {
            Result $false 'task_control_empty'
            exit 0
        }
        $item = @{ name = $name; id = $id; role = $focused.Current.ControlType.ProgrammaticName }
        Result $true 'bound_project' @($item)
        exit 0
    }
    if ($request.operation -eq 'bind') {
        if ($null -eq $focused -or $focused.Current.ProcessId -ne $pidTarget) {
            Result $false 'input_not_focused'
            exit 0
        }
        $pattern = $null
        $editable = $focused.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit
        if ($focused.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
            $editable = -not $pattern.Current.IsReadOnly
        }
        $nonChat = ($focused.Current.Name + ' ' + $focused.Current.AutomationId) -match '(?i)search|filter|address|\u641c\u7d22|\u67e5\u627e|\u7b5b\u9009|\u5730\u5740'
        if (-not $editable -or -not $focused.Current.IsKeyboardFocusable -or $focused.Current.IsPassword -or $nonChat) {
            Result $false 'focused_control_not_editable'
            exit 0
        }
        $item = @{ name = $focused.Current.Name; id = $focused.Current.AutomationId;
                   role = $focused.Current.ControlType.ProgrammaticName }
        Result $true 'bound_input' @($item)
        exit 0
    }
    if ($request.operation -eq 'check') {
        $found = @($edits | Where-Object { $_.Equals($focused) })
        Result ($found.Count -eq 1) 'focus_checked'
        exit 0
    }
    if ($request.operation -ne 'focus') { Result $false 'unknown_operation'; exit 0 }
    if (-not $request.name -and -not $request.id) {
        $alreadyFocused = @($edits | Where-Object { $_.Equals($focused) })
        if ($alreadyFocused.Count -eq 1) { $edits = $alreadyFocused }
    }
    if ($edits.Count -ne 1) { Result $false 'input_missing_or_ambiguous'; exit 0 }
    $edits[0].SetFocus()
    $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
    Result ($edits[0].Equals($focused)) 'input_focused'
} catch {
    Result $false 'uia_error'
}
